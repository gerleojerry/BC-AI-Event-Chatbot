import os
import requests
import time
from dotenv import load_dotenv


load_dotenv()

PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
API_URL = f"https://graph.facebook.com/v25.0/{PHONE_NUMBER_ID}/messages"

def send_template_message(phone_number: str, user_name: str):
    print(f"{phone_number=} - {user_name=}")
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }


    payload = {

            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone_number,
            "type": "template",
            "template": {
                "name": "event_reminder",
                "language": {
                    "code": "en"
                },
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {
                                "type": "text",
                                "parameter_name": "user_name",
                                "text": user_name 
                            }
                                        ]
                    }
                                ]
                    }
                }
    
    

    response = requests.post(API_URL, json=payload, headers=headers)
    return response.json()


# Send to a list of numbers
recipients = [
    {"phone": "2348164123725", "name": "Ayo"},
    {"phone": "2348069596373", "name": "Peter"},
   
]

for recipient in recipients:
    result = send_template_message(
        phone_number=recipient["phone"],
        user_name=recipient["name"],
    )
    print(f"Sent to {recipient['phone']}: {result}")
    time.sleep(3)
print("All sent!!!")