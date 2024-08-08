import requests
import json

url = "http://127.0.0.1:5000/query_lead"
headers = {
    "Content-Type": "application/json"
}
data = {
    "lead_id": "00Q2H00002GOYd1UAH"
}

response = requests.post(url, headers=headers, data=json.dumps(data))
print(response.json())
