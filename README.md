# Telegram bot for network status management

This project has for purpose to be able to check the availability of local network devices (e.g home network) through a telegram bot.

## Features

- **Activity logging** : Logs all activity into `bot_activity.log`
- **User white list** : Robbi can filter users access based on a preconfigured whitelist.
- **Highly customizable** : You can use your own API keys and update with your own commands.

## How to configure

The `topology.json` file describes all the usefull informations for Robbi.

```json
{
    "token": "YOUR_API_KEY",
    "white_list": {
        "userid": "YOUR_USER_ID"
    },
    "massa_address": "YOUR_MASSA_ADDRESS",
    "ninja_key" : "YOUR_NINJA_API_KEY"
}
```

## Commands

- `/hello` : Say hello.

- `/massa` : Retrieve info from your massa node, such as roll count, validated cycles, missed cycles and balance.

- `/btc` : Get bitcoin price, variation, high, low and volume.

## Prerequis

- Python 3.x
- A telegram account and a bot created thanks to [BotFather](https://core.telegram.org/bots#botfather).
- Python libraries : `python-telegram-bot`, `requests`, `json`, `logging`

## Links

[API-NINJA](https://www.api-ninjas.com/)

[MASSA JSON RPC API](https://docs.massa.net/docs/build/api/jsonrpc)