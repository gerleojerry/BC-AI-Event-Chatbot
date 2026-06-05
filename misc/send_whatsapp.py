import os
import logging

from twilio.rest import Client

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = os.getenv("TWILIO_NUMBER")


client = Client(account_sid, auth_token)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sedning message logiv through Twilio

def twilio_send_message(to_number, msg):
    print(f"{msg=}")
    print(f"{to_number=}")
    try:
        message = client.messages.create(
            from_=f"whatsapp:{twilio_number}",
            body=msg,
            to=f"whatsapp:{to_number}"
        )
        print(f"{message.body}")
        logger.info(f"Message sent successfully to {to_number}! SID: {message.sid}")
        return message
    except Exception as e:
        logger.error(f"Failed to send message to {to_number}: {e}")
        return None
