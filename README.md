# Telegram bot for network status management

This project has for purpose to be able to check the availability of local network devices (e.g home network) through a telegram bot.

## Features

- **Check the network status** : Robbi can ping local devices and says if it's still online or not.
- **Massa node status** : Robbi can ping a specific massa node and tell details about it.
- **User white list** : Robbi can filter users access based on a preconfigured whitelist.

## How to configure

The `topology.json` file describes all the usefull informations for Robbi

```json
{
    "token": "YOUR_API_KEY",
    "white_list": {
        "userid": "YOUR_USER_ID"
    },
    "massa_address": "YOUR_MASSA_ADDRESS"
}
```

## Prerequis

- Python 3.x
- A telegram account and a bot created thanks to [BotFather](https://core.telegram.org/bots#botfather).
- Python libraries : `python-telegram-bot`, `requests`, `json`, `logging`
