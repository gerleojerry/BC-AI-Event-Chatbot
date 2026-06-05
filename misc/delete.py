# # Handle incoming messages
# @app.post("/webhook")
# async def handle_webhook(request: Request):
#     data = await request.json()
#     print("Received webhook:", data)

#     if data:
#         for entry in data.get("entry", []):
#             for change in entry.get("changes", []):
#                 value = change.get("value", {})
#                 phone_number_id = value.get("metadata", {}).get("phone_number_id")
#                 message_data = value.get("messages", [])
#                 for message in message_data:
#                     # handle_message(message, phone_number_id)
#                     pass

#     return {"status": "EVENT_RECEIVED"}





# import requests
# import os
# from dotenv import load_dotenv

# load_dotenv()
# ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

# def send_message(to, message, phone_number_id):
#     url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
#     headers = {
#         "Authorization": f"Bearer {ACCESS_TOKEN}",
#         "Content-Type": "application/json"
#     }
#     payload = {
#         "messaging_product": "whatsapp",
#         "to": to,
#         "text": {"body": message}
#     }
#     response = requests.post(url, json=payload, headers=headers)
#     if response.status_code != 200:
#         print(f"Failed to send message to {to}. Response: {response.status_code} {response.text}")
#     else:
#         print(f"Message sent to {to}.")




import qrcode
from urllib.parse import quote

# WhatsApp number
phone_number = "+15559697072"

# Message
message = (
    "Hello, I would like to sign up and receive assistance "
    "from the BlueChip AI Summit 2026 chatbot."
)

# Encode message
encoded_message = quote(message)

# WhatsApp link
whatsapp_link = f"https://wa.me/{phone_number}?text={encoded_message}"

# Create high-quality QR code
qr = qrcode.QRCode(
    version=None,
    error_correction=qrcode.constants.ERROR_CORRECT_H,
    box_size=20,
    border=5
)

qr.add_data(whatsapp_link)
qr.make(fit=True)

# Generate image
img = qr.make_image(fill_color="black", back_color="white")

# Save high-resolution PNG
img.save("bluechip_ai_summit_qr.png")

print("High-quality QR Code generated successfully!")
print(whatsapp_link)