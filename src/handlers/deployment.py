import logging
import os
from telegram import Update
from telegram.ext import CallbackContext

from handlers.common import auth_required
from services.massa_version import (
    DEFAULT_MASSA_DOCKERFILE,
    read_massa_version,
    update_massa_version,
)


def _massa_dockerfile_path() -> str:
    return os.environ.get('MASSA_DOCKERFILE_PATH', DEFAULT_MASSA_DOCKERFILE)


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
        "Le conteneur en cours n'est pas modifié. Pour construire et démarrer "
        "cette version, exécutez `docker-compose up -d --build massa` sur l'hôte."
    )
