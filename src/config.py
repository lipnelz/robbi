import logging


# Scheduler
JOB_SCHED_NAME = 'periodic_node_ping'

# Logging
LOG_FILE_NAME = 'bot_activity.log'

# Conversation states
FLUSH_CONFIRM_STATE = 1
HIST_CONFIRM_STATE = 2

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

# File paths
BALANCE_HISTORY_FILE = 'config/balance_history.json'
PNG_FILE_NAME = 'plot.png'

# Scheduler interval
SCHEDULER_INTERVAL_MINUTES = 60

# Bot commands
COMMANDS_LIST = [
    {'id': 0, 'cmd_txt': 'hi', 'cmd_desc': 'Say hi to Robbi'},
    {'id': 1, 'cmd_txt': 'node', 'cmd_desc': 'Get node results'},
    {'id': 2, 'cmd_txt': 'btc', 'cmd_desc': 'Get BTC current price'},
    {'id': 3, 'cmd_txt': 'mas', 'cmd_desc': 'Get MAS current price'},
    {'id': 4, 'cmd_txt': 'hist', 'cmd_desc': 'Get node balance history'},
    {'id': 5, 'cmd_txt': 'flush', 'cmd_desc': 'Flush local logs'},
    {'id': 6, 'cmd_txt': 'temperature', 'cmd_desc': 'Get system temperature, CPU and RAM'},
]

# Configure logging module
def setup_logging():
    logging.basicConfig(
        filename=LOG_FILE_NAME,
        filemode='a',
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
