import requests
import json

def get_status(address: str) -> None:
    """
    Print the status from a given address

    :param address: The address to querry.
    """
    # Define API and URL
    url = 'https://mainnet.massa.net/api/v2'
    headers = {
        'Content-Type': 'application/json'
    }
    data = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "get_status",
         "params": [[address]]
    }

    try:
        # Send POST request
        response = requests.post(url, headers=headers, data=json.dumps(data))
        # Check response status
        if response.status_code == 200:
            # Parse JSON
            response_json = response.json()
            print(json.dumps(response_json, indent=4))
        else:
            print(f"Error: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")

def get_addresses(address: str) -> dict:
    # Define API and URL
    url = 'https://mainnet.massa.net/api/v2'
    headers = {
        'Content-Type': 'application/json'
    }
    data = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "get_addresses",
         "params": [[address]]
    }

    try:
        # Send POST request
        response = requests.post(url, headers=headers, data=json.dumps(data))
        # Check response status
        if response.status_code == 200:
            # Parse JSON
            response_json = response.json()
            print(json.dumps(response_json, indent=4))
            return response_json
        else:
            print(f"Error: {response.status_code}")
            return {}
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return {}