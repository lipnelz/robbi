import logging


# Scheduler
JOB_SCHED_NAME = 'periodic_node_ping'

# Logging
LOG_FILE_NAME = 'bot_activity.log'

# Conversation states
FLUSH_CONFIRM_STATE = 1
HIST_CONFIRM_STATE = 2
DOCKER_MENU_STATE = 3
DOCKER_START_CONFIRM_STATE = 4
DOCKER_STOP_CONFIRM_STATE = 5
DOCKER_MASSA_MENU_STATE = 6
DOCKER_BUYROLLS_INPUT_STATE = 7
DOCKER_BUYROLLS_CONFIRM_STATE = 8
DOCKER_SELLROLLS_INPUT_STATE = 9
DOCKER_SELLROLLS_CONFIRM_STATE = 10
DOCKER_RESTART_CONFIRM_STATE = 11

# Media files
BUDDY_FILE_NAME = 'Buddy_christ.jpg'
PAT_FILE_NAME = 'patrick.gif'
BTC_CRY_NAME = "btc_cry.png"
MAS_CRY_NAME = "mas_cry.png"
TIMEOUT_NAME = "timeout.png"
TIMEOUT_FIRE_NAME = "timeout_fire.png"

# Node status messages
NODE_IS_DOWN = 'Node is down'
NODE_IS_UP = 'Node is up and running'

# Bot commands
COMMANDS_LIST = [
    {'id': 11, 'cmd_txt': 'menu', 'cmd_desc': 'Open the main menu'},
    {'id': 12, 'cmd_txt': 'help', 'cmd_desc': 'Show help and shortcuts'},
    {'id': 0, 'cmd_txt': 'hi', 'cmd_desc': 'Say hi to Robbi'},
    {'id': 1, 'cmd_txt': 'node', 'cmd_desc': 'Get node results'},
    {'id': 2, 'cmd_txt': 'btc', 'cmd_desc': 'Get BTC current price'},
    {'id': 3, 'cmd_txt': 'mas', 'cmd_desc': 'Get MAS current price'},
    {'id': 4, 'cmd_txt': 'hist', 'cmd_desc': 'Get node balance history'},
    {'id': 5, 'cmd_txt': 'flush', 'cmd_desc': 'Flush local logs'},
    {'id': 6, 'cmd_txt': 'temperature', 'cmd_desc': 'Get system temperature, CPU and RAM'},
    {'id': 7, 'cmd_txt': 'perf', 'cmd_desc': 'Get RPC latency and observed node availability'},
    {'id': 8, 'cmd_txt': 'docker', 'cmd_desc': 'Manage Docker containers (start/stop/restart)'},
    {'id': 9, 'cmd_txt': 'status', 'cmd_desc': 'Check Massa node startup, health and activity'},
    {'id': 10, 'cmd_txt': 'massa_version', 'cmd_desc': 'Show or update the Massa Docker build version'},
]

# Configure logging module
logging.basicConfig(
    filename=LOG_FILE_NAME,
    filemode='a',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# httpx logs full request URLs, which contain the Telegram bot token
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
