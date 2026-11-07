import asyncio
import logging
import os
from telegram import Update
from telegram.ext import CallbackContext

from handlers.common import auth_required
from services.massa_deployment import rebuild_massa
from services.massa_version import (
    DEFAULT_MASSA_DOCKERFILE,
    read_massa_version,
    update_massa_version,
)


def _massa_dockerfile_path() -> str:
    return os.environ.get('MASSA_DOCKERFILE_PATH', DEFAULT_MASSA_DOCKERFILE)


async def _rebuild_massa_and_report(message, version: str) -> None:
    try:
        result = await asyncio.to_thread(rebuild_massa)
        if result.returncode:
            details = (result.stderr or result.stdout).strip()
            logging.error("Massa Compose rebuild failed: %s", details)
            response = f"❌ Échec du rebuild de Massa (code {result.returncode})."
            if details:
                response += f"\n{details[-2500:]}"
        else:
            logging.info("Massa %s rebuilt and recreated successfully.", version)
            response = f"✅ Massa a été reconstruit et redémarré en version {version}."
    except Exception as error:
        logging.exception("Unable to rebuild Massa with Docker Compose.")
        response = f"❌ Impossible de reconstruire Massa : {error}"

    try:
        await message.reply_text(response)
    except Exception:
        logging.exception("Could not report Massa rebuild result to Telegram.")


@auth_required
async def massa_version(update: Update, context: CallbackContext) -> None:
    """Show or update the Massa Dockerfile's default build version."""
    dockerfile_path = _massa_dockerfile_path()

    if len(context.args) == 0:
        try:
            current_version = read_massa_version(dockerfile_path)
        except (OSError, ValueError) as error:
            logging.error("Unable to read Massa Dockerfile version: %s", error)
            await update.message.reply_text(f"Impossible de lire la version Massa : {error}")
            return
        await update.message.reply_text(
            f"Version Massa configurée : {current_version}\n"
            "Pour la modifier : /massa_version MAIN.5.2"
        )
        return

    if len(context.args) != 1:
        await update.message.reply_text(
            "Usage : /massa_version <version> (ex. /massa_version MAIN.5.2)"
        )
        return

    try:
        previous_version, new_version = update_massa_version(
            context.args[0],
            dockerfile_path,
        )
    except (OSError, ValueError) as error:
        logging.error("Unable to update Massa Dockerfile version: %s", error)
        await update.message.reply_text(f"Version Massa non modifiée : {error}")
        return

    logging.info(
        "User %s changed the Massa build version from %s to %s.",
        update.effective_user.id,
        previous_version,
        new_version,
    )
    await update.message.reply_text(
        f"✅ Version Massa modifiée : {previous_version} → {new_version}.\n"
        "⏳ Je reconstruis et redémarre le conteneur Massa. Je t'enverrai le résultat."
    )
    context.application.create_task(
        _rebuild_massa_and_report(update.message, new_version)
    )
