import requests

response = requests.post(
    "http://localhost:8000/call/initiate",
    json={
        "To": "+4915906752100",  # Your test phone number
        "call_purpose": "test call",
        "context": {"test": "true"}
    }
)

print(response)