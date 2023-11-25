import requests
import json

def send_json_post(endpoint, data):
    """
    Send a JSON POST request to a specified endpoint.

    Parameters:
    - endpoint (str): The URL where the request should be sent.
    - data (dict): The JSON data to be sent in the request payload.

    Returns:
    - dict: The JSON response from the server.
    """
    # Convert the data to JSON format
    json_data = json.dumps(data)

    # Set the headers for the request
    headers = {
        'Content-Type': 'application/json',
    }

    # Make the POST request
    response = requests.post(endpoint, data=json_data, headers=headers)

    # Check if the request was successful (status code 2xx)
    if response.ok:
        print("POST Successful")
    else:
        # If the request was unsuccessful, raise an exception with the error message
        response.raise_for_status()

# Example usage:
endpoint_url = "http://localhost:5000"
json_data_to_send = {"SteamId": "123456", "EventType":"Follow"}

try:
    response_data = send_json_post(endpoint_url, json_data_to_send)
    print("Response from server:", response_data)
except requests.exceptions.RequestException as e:
    print("Error:", e)