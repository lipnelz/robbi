import logging
from types import SimpleNamespace
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup,
)
from telegram.ext import CallbackContext, ConversationHandler
from config import COMMANDS_LIST, DOCKER_MENU_STATE
from handlers.common import auth_required, cb_auth_required
from handlers.node import (
    node, flush, hist, _DOCKER_MENU_TEXT, _build_docker_main_menu_markup,
)
from handlers.price import btc, mas
from handlers.system import hi, temperature, perf
from handlers.node_status import node_status
from handlers.deployment import massa_version


MENU_BUTTON_LABEL = "🏠 Menu"
_MAX_TEXT_LENGTH = 4000
_LOADING_TEXT = "⏳ Loading…"

_MAIN_TEXT = "🤖 Robbi — what do you want to do?"
_MONITORING_TEXT = "📊 Monitoring\nChoose a check:"
_CRYPTO_TEXT = "💰 Crypto\nChoose a price:"
_DATA_TEXT = "🧹 Data\nChoose an action:"

# Actions run through the existing command handlers.
# key -> (handler, parent menu callback, optional related action shortcut)
_ACTIONS = {
    'node': (node, 'menu_monitoring', None),
    'temperature': (temperature, 'menu_monitoring', None),
    'perf': (perf, 'menu_monitoring', None),
    'status': (node_status, 'menu_monitoring', None),
    'massa_version': (massa_version, 'menu_monitoring', None),
    'hi': (hi, 'menu_monitoring', None),
    'btc': (btc, 'menu_crypto', ('🟣 MAS', 'menu_run_mas')),
    'mas': (mas, 'menu_crypto', ('₿ BTC', 'menu_run_btc')),
}

# Handlers whose combined text output forms the quick summary.
_SUMMARY_HANDLERS = (perf, temperature, btc, mas)


def _button(label: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(label, callback_data=data)


def build_main_menu_markup() -> InlineKeyboardMarkup:
    """Build the top-level menu keyboard."""
    return InlineKeyboardMarkup([
        [_button("📊 Monitoring", 'menu_monitoring'), _button("💰 Crypto", 'menu_crypto')],
        [_button("🐳 Node & Docker", 'menu_docker'), _button("🧹 Data", 'menu_data')],
        [_button("📋 Summary", 'menu_summary'), _button("❓ Help", 'menu_help')],
    ])


def _build_monitoring_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_button("🖥️ Node", 'menu_run_node'), _button("🌡️ System", 'menu_run_temperature')],
        [_button("⚡ Performance", 'menu_run_perf'), _button("🔎 Status", 'menu_run_status')],
        [_button("🏷️ Massa version", 'menu_run_massa_version'), _button("👋 Hi", 'menu_run_hi')],
        [_button("⬅️ Back", 'menu_home')],
    ])


def _build_crypto_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_button("₿ BTC", 'menu_run_btc'), _button("🟣 MAS", 'menu_run_mas')],
        [_button("📋 Summary", 'menu_summary')],
        [_button("⬅️ Back", 'menu_home')],
    ])


def _build_data_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_button("📈 Balance history", 'menu_hist'), _button("🧹 Flush logs", 'menu_flush')],
        [_button("⬅️ Back", 'menu_home')],
    ])


def _build_nav_markup(refresh: str = None, parent: str = 'menu_home', extra: tuple = None) -> InlineKeyboardMarkup:
    """Footer shown under a result: refresh, related shortcut, back and home."""
    first_row = []
    if refresh:
        first_row.append(_button("🔄 Refresh", refresh))
    if extra:
        first_row.append(_button(*extra))
    rows = [first_row] if first_row else []
    second_row = []
    if parent != 'menu_home':
        second_row.append(_button("⬅️ Back", parent))
    second_row.append(_button(MENU_BUTTON_LABEL, 'menu_home'))
    rows.append(second_row)
    return InlineKeyboardMarkup(rows)


def _build_help_text() -> str:
    lines = ["❓ Help", "Everything is reachable from /menu. Shortcuts:", ""]
    lines += [f"/{cmd['cmd_txt']} — {cmd['cmd_desc']}" for cmd in COMMANDS_LIST]
    return "\n".join(lines)


class _ReplyCollector:
    """Stand-in for update.message used when a command handler runs from a button.

    Text replies are buffered so they can be shown by editing the menu message;
    a photo flushes the buffered text first to keep the original order.
    """

    def __init__(self, bot, chat_id):
        self._bot = bot
        self._chat_id = chat_id
        self.pending = []
        self.sent_any = False

    async def reply_text(self, text, **kwargs):
        self.pending.append(text)

    async def reply_photo(self, photo, **kwargs):
        await self.flush()
        await self._bot.send_photo(chat_id=self._chat_id, photo=photo)
        self.sent_any = True

    async def flush(self):
        for text in self.pending:
            await self._bot.send_message(chat_id=self._chat_id, text=text)
            self.sent_any = True
        self.pending = []


def _make_update_proxy(query, message) -> SimpleNamespace:
    """Build an Update-like object so existing command handlers work from a button click."""
    return SimpleNamespace(
        effective_user=query.from_user,
        effective_chat=query.message.chat,
        message=message,
        callback_query=query,
    )


def _ensure_args(context: CallbackContext) -> None:
    if getattr(context, 'args', None) is None:
        context.args = []


async def _safe_edit(query, text: str, markup: InlineKeyboardMarkup = None) -> None:
    try:
        await query.edit_message_text(text=text[:_MAX_TEXT_LENGTH], reply_markup=markup)
    except Exception as e:
        # Typically "message is not modified" when refreshing identical content
        logging.debug("Menu edit skipped: %s", e)


async def _show_menu(query, text: str, markup: InlineKeyboardMarkup) -> None:
    await query.answer()
    await _safe_edit(query, text, markup)


async def _finish_run(query, collector, markup: InlineKeyboardMarkup) -> None:
    """Show the buffered output in place, or below already-sent media with a nav footer."""
    text = "\n\n".join(collector.pending) or "✅ Done"
    if not collector.sent_any:
        await _safe_edit(query, text, markup)
        return
    try:
        await query.message.delete()
    except Exception as e:
        logging.debug("Menu message deletion skipped: %s", e)
    await query.get_bot().send_message(
        chat_id=query.message.chat_id,
        text=text[:_MAX_TEXT_LENGTH] if collector.pending else "✅ Done",
        reply_markup=markup,
    )


async def _run_handlers(query, context, handlers) -> _ReplyCollector:
    collector = _ReplyCollector(context.bot, query.message.chat_id)
    proxy = _make_update_proxy(query, collector)
    _ensure_args(context)
    for handler in handlers:
        try:
            await handler(proxy, context)
        except Exception as e:
            logging.error("Error running %s from menu: %s", handler.__name__, e)
            collector.pending.append("⚠️ An error occurred.")
    return collector


@auth_required
async def menu(update: Update, context: CallbackContext) -> None:
    """Handle /menu, /help: show the main menu."""
    logging.info(f'User {update.effective_user.id} used the /menu command.')
    await update.message.reply_text(_MAIN_TEXT, reply_markup=build_main_menu_markup())


@auth_required
async def start(update: Update, context: CallbackContext) -> None:
    """Handle /start: install the persistent Menu button, then show the main menu."""
    logging.info(f'User {update.effective_user.id} used the /start command.')
    keyboard = ReplyKeyboardMarkup(
        [[MENU_BUTTON_LABEL]], resize_keyboard=True, is_persistent=True,
    )
    await update.message.reply_text("👋 Hi! Use the 🏠 Menu button anytime.", reply_markup=keyboard)
    await update.message.reply_text(_MAIN_TEXT, reply_markup=build_main_menu_markup())


@cb_auth_required
async def menu_home(update: Update, context: CallbackContext) -> int:
    """Callback: back to the main menu (also leaves any active docker conversation)."""
    await _show_menu(update.callback_query, _MAIN_TEXT, build_main_menu_markup())
    return ConversationHandler.END


@cb_auth_required
async def menu_monitoring(update: Update, context: CallbackContext) -> None:
    await _show_menu(update.callback_query, _MONITORING_TEXT, _build_monitoring_markup())


@cb_auth_required
async def menu_crypto(update: Update, context: CallbackContext) -> None:
    await _show_menu(update.callback_query, _CRYPTO_TEXT, _build_crypto_markup())


@cb_auth_required
async def menu_data(update: Update, context: CallbackContext) -> None:
    await _show_menu(update.callback_query, _DATA_TEXT, _build_data_markup())


@cb_auth_required
async def menu_help(update: Update, context: CallbackContext) -> None:
    await _show_menu(update.callback_query, _build_help_text(), _build_nav_markup())


@cb_auth_required
async def menu_run(update: Update, context: CallbackContext) -> None:
    """Callback: run one command handler from a button and show its result."""
    query = update.callback_query
    action = query.data[len('menu_run_'):]
    if action not in _ACTIONS:
        await _show_menu(query, _MAIN_TEXT, build_main_menu_markup())
        return
    handler, parent, extra = _ACTIONS[action]
    logging.info(f'User {query.from_user.id} ran {action} from the menu.')
    await query.answer()
    await _safe_edit(query, _LOADING_TEXT)
    collector = await _run_handlers(query, context, [handler])
    await _finish_run(query, collector, _build_nav_markup(f'menu_run_{action}', parent, extra))


@cb_auth_required
async def menu_summary(update: Update, context: CallbackContext) -> None:
    """Callback: one-message dashboard combining performance, system and prices."""
    query = update.callback_query
    logging.info(f'User {query.from_user.id} requested the summary from the menu.')
    await query.answer()
    await _safe_edit(query, _LOADING_TEXT)
    collector = await _run_handlers(query, context, list(_SUMMARY_HANDLERS))
    await _finish_run(query, collector, _build_nav_markup('menu_summary'))


@cb_auth_required
async def menu_docker(update: Update, context: CallbackContext) -> int:
    """Callback (docker conversation entry point): open the docker menu."""
    query = update.callback_query
    await query.answer()
    await _safe_edit(query, _DOCKER_MENU_TEXT, _build_docker_main_menu_markup())
    return DOCKER_MENU_STATE


async def _enter_from_menu(update: Update, context: CallbackContext, title: str, entry) -> int:
    query = update.callback_query
    await query.answer()
    await _safe_edit(query, title)
    return await entry(_make_update_proxy(query, query.message), context)


@cb_auth_required
async def menu_hist(update: Update, context: CallbackContext) -> int:
    """Callback (hist conversation entry point): run /hist from the Data menu."""
    return await _enter_from_menu(update, context, "📈 Balance history", hist)


@cb_auth_required
async def menu_flush(update: Update, context: CallbackContext) -> int:
    """Callback (flush conversation entry point): run /flush from the Data menu."""
    return await _enter_from_menu(update, context, "🧹 Flush logs", flush)


async def menu_expired(update: Update, context: CallbackContext) -> None:
    """Callback: answer buttons whose conversation no longer exists (e.g. after a restart)."""
    query = update.callback_query
    await query.answer("This menu has expired. Use /menu.", show_alert=True)


async def menu_button_text(update: Update, context: CallbackContext) -> None:
    """Message handler: the persistent Menu keyboard button opens the main menu."""
    await menu(update, context)
