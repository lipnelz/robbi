import logging


def _get_docker_client():
    """Create a Docker client connected via the mounted socket."""
    import docker
    return docker.from_env()


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
