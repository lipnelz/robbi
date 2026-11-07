import asyncio
import logging
from telegram import Update
from telegram.ext import CallbackContext

from handlers.common import auth_required
from services.docker_manager import get_container_status
from services.massa_rpc import DEFAULT_MASSA_RPC_URL, get_node_status


def _slot_text(slot) -> str:
    if not isinstance(slot, dict):
        return "indisponible"
    period = slot.get('period')
    thread = slot.get('thread')
    if period is None or thread is None:
        return "indisponible"
    return f"période {period}, thread {thread}"


def _format_massa_status(result: dict) -> str:
    """Format the fields Massa exposes in the get_status response."""
    status = result.get('result')
    if not isinstance(status, dict):
        raise ValueError("Réponse get_status invalide.")

    lines = ["📡 État RPC Massa : disponible"]
    version = status.get('version')
    if version:
        lines.append(f"Version : {version}")
    cycle = status.get('current_cycle')
    if cycle is not None:
        lines.append(f"Cycle courant : {cycle}")

    network_stats = status.get('network_stats')
    connected_nodes = status.get('connected_nodes')
    peers = network_stats.get('active_node_count') if isinstance(network_stats, dict) else None
    if peers is None and isinstance(connected_nodes, dict):
        peers = len(connected_nodes)
    if peers is not None:
        lines.append(f"Nœuds pairs connectés : {peers}")

    last_slot = status.get('last_slot')
    if last_slot:
        lines.append(f"Dernier slot : {_slot_text(last_slot)}")
    next_slot = status.get('next_slot')
    if next_slot:
        lines.append(f"Prochain slot : {_slot_text(next_slot)}")

    consensus = status.get('consensus_stats')
    execution = status.get('execution_stats')
    activity = []
    if isinstance(consensus, dict):
        blocks = consensus.get('final_block_count')
        stale_blocks = consensus.get('stale_block_count')
        if blocks is not None:
            activity.append(f"{blocks} blocs finalisés dans la fenêtre récente")
        if stale_blocks is not None:
            activity.append(f"{stale_blocks} blocs obsolètes")
    if isinstance(execution, dict):
        operations = execution.get('final_executed_operations_count')
        if operations is not None:
            activity.append(f"{operations} opérations exécutées dans la fenêtre récente")
        final_cursor = execution.get('final_cursor')
        active_cursor = execution.get('active_cursor')
        if final_cursor or active_cursor:
            activity.append(
                f"curseur d'exécution final : {_slot_text(final_cursor)}, "
                f"actif : {_slot_text(active_cursor)}"
            )
    if activity:
        lines.append("Activité récente : " + " ; ".join(activity))

    return "\n".join(lines)


def _container_state_lines(container_status: dict) -> list[str]:
    if container_status.get('status') != 'ok':
        return [f"🐳 État du conteneur : indisponible ({container_status.get('message', 'erreur Docker')})"]

    state = container_status.get('state')
    labels = {
        'running': "démarré",
        'created': "créé, en attente de démarrage",
        'restarting': "en redémarrage",
        'paused': "en pause",
        'exited': "arrêté",
        'dead': "arrêté (état Docker « dead »)",
        'removing': "en cours de suppression",
    }
    lines = [f"🐳 Conteneur Massa : {labels.get(state, state or 'état inconnu')}"]
    health = container_status.get('health')
    if health:
        health_labels = {
            'healthy': "sain",
            'starting': "vérification en cours",
            'unhealthy': "non sain",
        }
        lines.append(f"Healthcheck : {health_labels.get(health, health)}")
    if state == 'exited' and container_status.get('exit_code') is not None:
        lines.append(f"Code de sortie : {container_status['exit_code']}")
    if container_status.get('error'):
        lines.append(f"Erreur Docker : {container_status['error']}")
    return lines


@auth_required
async def node_status(update: Update, context: CallbackContext) -> None:
    """Report Docker process state and live Massa node activity."""
    logging.info("User %s used the /status command.", update.effective_user.id)
    container_name = context.bot_data.get('node_container_name', 'massa-container')
    rpc_url = context.bot_data.get('massa_node_rpc_url', DEFAULT_MASSA_RPC_URL)

    try:
        container_status = await asyncio.to_thread(
            get_container_status, logging, container_name
        )
        lines = ["🔎 État du nœud Massa", *_container_state_lines(container_status)]

        if container_status.get('status') == 'ok' and container_status.get('state') != 'running':
            lines.append("RPC : non interrogé, car le conteneur n'est pas démarré.")
        else:
            rpc_result = await asyncio.to_thread(get_node_status, logging, rpc_url)
            if "error" in rpc_result:
                lines.append(
                    "📡 RPC Massa : indisponible "
                    "(le nœud peut démarrer, ou rencontrer un problème)."
                )
                lines.append(f"Détail : {rpc_result['error']}")
            else:
                lines.append(_format_massa_status(rpc_result))

        await update.message.reply_text("\n".join(lines))
    except (TypeError, ValueError, KeyError) as error:
        logging.error("Invalid Massa node status response: %s", error)
        await update.message.reply_text("Impossible d'interpréter la réponse d'état du nœud Massa.")
    except Exception as error:
        logging.exception("Error retrieving Massa node status")
        await update.message.reply_text(f"Erreur lors de la vérification du nœud Massa : {error}")
