import logging


def _get_docker_client():
    """Create a Docker client connected via the mounted socket."""
    import docker
    return docker.from_env()


def _is_image_allowed(image_ref: str, allowed_images: list[str] | None) -> bool:
    """Return True when the image reference is allowed by exact or repository match."""
    if not allowed_images:
        return True

    normalized = image_ref.strip()
    repository = normalized.split(':', 1)[0]
    return normalized in allowed_images or repository in allowed_images


def start_docker_node(logger, container_name: str) -> dict:
    """
    Start a Docker container running the Massa node.

    :param logger: The logger instance
    :param container_name: Name of the Docker container (e.g., 'massa-node')
    :return: dict with status and message
    """
    if logger is None:
        logger = logging.getLogger()

    try:
        client = _get_docker_client()
        container = client.containers.get(container_name)
        container.start()
        logger.info(f"Docker container '{container_name}' started successfully.")
        return {"status": "ok", "message": f"✅ Container '{container_name}' started."}
    except Exception as e:
        logger.error(f"Error starting Docker container: {e}")
        return {"status": "error", "message": f"❌ Error: {str(e)}"}


def stop_docker_node(logger, container_name: str) -> dict:
    """
    Stop a Docker container running the Massa node.

    :param logger: The logger instance
    :param container_name: Name of the Docker container (e.g., 'massa-container')
    :return: dict with status and message
    """
    if logger is None:
        logger = logging.getLogger()

    try:
        client = _get_docker_client()
        container = client.containers.get(container_name)
        container.stop(timeout=30)
        logger.info(f"Docker container '{container_name}' stopped successfully.")
        return {"status": "ok", "message": f"✅ Container '{container_name}' stopped."}
    except Exception as e:
        logger.error(f"Error stopping Docker container: {e}")
        return {"status": "error", "message": f"❌ Error: {str(e)}"}


def exec_massa_client(logger, container_name: str, password: str, command: str) -> dict:
    """
    Execute a command via massa-client inside a Docker container.

    :param logger: The logger instance
    :param container_name: Name of the Docker container
    :param password: Massa client password
    :param command: The massa-client command to execute (e.g. 'wallet_info')
    :return: dict with status, message/output
    """
    if logger is None:
        logger = logging.getLogger()

    try:
        client = _get_docker_client()
        container = client.containers.get(container_name)
        cmd = ['./massa-client', '-p', password, '-a'] + command.split()
        exit_code, output = container.exec_run(cmd, workdir='/massa/massa-client')
        decoded = output.decode('utf-8', errors='replace').strip()

        # Send exit command to cleanly close the massa-client session
        exit_cmd = ['./massa-client', '-p', password, '-a', 'exit']
        container.exec_run(exit_cmd, workdir='/massa/massa-client')

        if exit_code == 0:
            logger.info(f"massa-client command '{command}' executed successfully.")
            return {"status": "ok", "output": decoded}
        else:
            logger.error(f"massa-client command failed: {decoded}")
            return {"status": "error", "message": f"❌ Command failed:\n{decoded}"}
    except Exception as e:
        logger.error(f"Error executing massa-client: {e}")
        return {"status": "error", "message": f"❌ Error: {str(e)}"}


def update_docker_container_image(
    logger,
    container_name: str,
    image_ref: str,
    allowed_images: list[str] | None = None,
) -> dict:
    """Update a running container by pulling image and recreating container with same settings."""
    if logger is None:
        logger = logging.getLogger()

    if not container_name or not image_ref:
        return {
            "status": "error",
            "message": "❌ Missing container name or image reference.",
        }

    if not _is_image_allowed(image_ref, allowed_images):
        logger.warning("Image '%s' refused by allowlist", image_ref)
        return {
            "status": "error",
            "message": "❌ Target image is not allowed.",
        }

    try:
        client = _get_docker_client()
        old_container = client.containers.get(container_name)
        old_container.reload()
        attrs = old_container.attrs

        config = attrs.get('Config', {})
        host_config = attrs.get('HostConfig', {})
        networking = attrs.get('NetworkSettings', {}).get('Networks', {})

        env = config.get('Env')
        command = config.get('Cmd')
        entrypoint = config.get('Entrypoint')
        working_dir = config.get('WorkingDir') or None
        labels = config.get('Labels') or {}
        user = config.get('User') or None
        volumes = host_config.get('Binds')
        restart_policy = host_config.get('RestartPolicy') or {}
        network_mode = host_config.get('NetworkMode')

        old_image_tags = old_container.image.tags or []
        old_image = old_image_tags[0] if old_image_tags else old_container.image.id

        logger.info("Pulling image '%s' for container '%s'", image_ref, container_name)
        client.images.pull(image_ref)

        candidate_name = f"{container_name}-candidate"
        # Cleanup orphan candidate from previous failed update.
        try:
            stale_candidate = client.containers.get(candidate_name)
            stale_candidate.remove(force=True)
        except Exception:
            pass

        logger.info("Creating candidate container '%s'", candidate_name)
        new_container = client.containers.create(
            image_ref,
            name=candidate_name,
            environment=env,
            command=command,
            entrypoint=entrypoint,
            working_dir=working_dir,
            labels=labels,
            user=user,
            detach=True,
            volumes=volumes,
            network_mode=network_mode,
            restart_policy=restart_policy,
        )

        try:
            # Re-attach explicit network aliases when multiple docker networks are in use.
            if network_mode == 'default' and networking:
                for net_name, net_data in networking.items():
                    net = client.networks.get(net_name)
                    aliases = net_data.get('Aliases')
                    net.connect(new_container, aliases=aliases)
        except Exception as net_err:
            logger.warning("Network reconnect warning for '%s': %s", container_name, net_err)

        new_container.start()

        logger.info("Switching from '%s' to new image '%s'", old_image, image_ref)
        old_container.stop(timeout=30)
        old_container.remove()
        new_container.rename(container_name)

        return {
            "status": "ok",
            "message": (
                f"✅ Container '{container_name}' updated from '{old_image}' to '{image_ref}'."
            ),
            "old_image": old_image,
            "new_image": image_ref,
        }
    except Exception as e:
        logger.error("Error updating Docker container image: %s", e)
        return {
            "status": "error",
            "message": f"❌ Error during update: {str(e)}",
        }
