# import os
# import logging
# from dotenv import load_dotenv
# from fastapi import FastAPI, Form
# from typing import Optional, Dict, Any
# from datetime import datetime, timezone
# from fastapi.middleware.cors import CORSMiddleware
# from motor.motor_asyncio import AsyncIOMotorClient
# from beanie import init_beanie
# from models import Session, Message, User, Request, Beneficiary 
# import prompts
# from vfd_helper import VFDHelper
# from utils import most_recent_beneficiaries
# from trans_req import recipient_type_detector,get_default_response,transfer_qa, get_transaction_request, get_transfer_response, extract_beneficiary_details, extract_transfer_details, get_current_beneficiary_transfer_name, beneficiary_transfer_response, get_account_balance
# from conversations import get_conversations, get_response, get_user_info, get_stage
# from send import twilio_send_message

# load_dotenv()
# logging.basicConfig(level=logging.INFO,  format='%(asctime)s - %(levelname)s - %(message)s',  handlers=[logging.FileHandler('app.log', mode='w'), logging.StreamHandler()])


# app = FastAPI()

# origins = ["*"]

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # @app.on_event("startup")
# # async def start_db():
# #     await init_db()

# @app.get("/health")
# async def root():
#     return {"response": "Seems good"}


# @app.post("/create")
# def create_user(): 
#     pass



# async def send_message(request: Request):

#     collection_name = 'bluechip'
#     mongo_string = os.getenv("MONGO_CONNECTION_STRING")

   
#     client = AsyncIOMotorClient(mongo_string)

#     await init_beanie(database=client[collection_name], document_models=[Session, User, Beneficiary])
#     current_time = datetime.now(timezone.utc).replace(tzinfo=timezone.utc).time()

#     user = await User.find_one({'phone_number' : request.phone_number})
#     logging.info(f"User : {user}")

#     if not user: 

#         session = await Session.find_one({"phone_number": request.phone_number})
#         message = Message(message = request.message , is_user = True)
#         result = "You are new user, Please click on this link to sign up."

    
#     else:
#         session = await Session.find_one({"phone_number": request.phone_number})
#         message = Message(message = request.message, is_user = True)
        
#         if session:
#             session.chats.append(message)
#             await session.save()
#             logging.info("User message saved to session")

#         else:
#             session = Session(phone_number=request.phone_number)
#             session.chats = [message]
#             await session.insert()
#             logging.info("New session created and user message saved.")

#         request_type = get_transaction_request(session, prompts.REQUEST_DETECTOR_PROMPT)
#         print(request_type.content)

#         if(request_type.content == "default"):
#             res = get_default_response(session, prompts.GENERAL_BOT_PROMPT)
#             result = res['response_message']
#             print("Default", result)
        
#         elif(request_type.content == "qa"):
#             res  = transfer_qa(session, prompts.TRANSFER_QA_PROMPT)
#             result = res['response_message']
#             print("Transfer QA response", result)

#         elif(request_type.content == "account_balance"):
#             res  = get_account_balance(session, prompts.ACCT_BAL_SYSTEM_PROMPT)
#             print("Account balance", res)
#             result = res['response_message']

#         elif(request_type.content == "transfer"):
#                 # Check if user already saw the transfer prompt
#             if not session.transfer_prompt_shown:
#                 recent_beneficiaries = await most_recent_beneficiaries(request.phone_number)
#                 lastfive = recent_beneficiaries[0]['last_five_beneficiaries']

#                 if recent_beneficiaries and 'last_five_beneficiaries' in recent_beneficiaries[0]:
#                     lastfive = recent_beneficiaries[0]['last_five_beneficiaries']
#                 else:
#                     lastfive = []
                    
#                 if lastfive:
#                     beneficiaries = "\n".join(
#                         [f"-{b['name']} ({b['account_number']}, {b['bank']})" for b in lastfive]
#                     )
#                     result = f"Ok! You recently transferred to: {beneficiaries}. Would you like to transfer to one of your beneficiaries or a new recipient?"
#                 else:
#                     result = "You don't have any beneficiaries yet. Would you like to transfer to a new recipient?"

#                 # Save flag to session
#                 session.transfer_prompt_shown = True
#                 await session.save()

#                 # Return early and wait for user reply
#                 message = Message(message=result, is_user=False)
#                 session.chats.append(message)
#                 await session.save()
#                 logging.info("Prompted user with beneficiaries. Awaiting reply.")
#                 return {"response": result}
            
#             # ---- Proceed to transfer logic after user replied ----
#             # Retrieve last five beneficiaries from the database
#             recent_beneficiaries = await most_recent_beneficiaries(request.phone_number)

#             print("Recent beneficiaries:", recent_beneficiaries)

#             lastfive = recent_beneficiaries[0]['last_five_beneficiaries'] 
#             print("Five beneficiaries: ",lastfive)

#             # Detect recipient type once and store in session
#             if not session.recipient_type or session.recipient_type is None:
#                 recipient_type_data = recipient_type_detector(lastfive, session, prompts.RECIPIENT_TYPE_DETECTOR)
#                 session.recipient_type = recipient_type_data['recipient_type']
#                 await session.save()
#                 logging.info("Recipient type detected and saved: %s", session.recipient_type)
#             else:
#                 logging.info("Using cached recipient type: %s", session.recipient_type)

#             recipient_type = session.recipient_type
#             logging.info("Recipient type detected:", recipient_type)

#             if recipient_type == "new":
#                 logging.info("Entered the new recipient phase!")
#                 # Pass to the model for transfer
#                 response = get_transfer_response(session, prompts.TRANSFER_AGENT_SYSTEM_PROMPT)
        
#                 print("Transfer request response :", response['is_request_completed'])
#                 is_request_completed = response['is_request_completed']

#                 logging.info("Transfer response:", response)     

#                 if is_request_completed:
#                     # Extract transfer details to process transfer
#                     transfer_details = extract_transfer_details(session, prompts.TRANSFER_DETAILS_PROMPT)
#                     print("Transfer Details of new recipient transfer process: ", transfer_details)
#                     process_transfer = VFDHelper.transfer_withdraw(session, transfer_details)
#                     print("Transfer endpoint output: ",process_transfer)

#                     #Extract recipient details to store as beneficiary
#                     extracted_recipient = extract_beneficiary_details(session, prompts.RECIPIENT_STORE_PROMPT)

#                     # Store recipient details as beneficiary in database
#                     # beneficiary = Beneficiary(phone_number = request.phone_number, name = extracted_recipient["recipientName"], account_number = extracted_recipient["recipientAccountNumber"],bank = extracted_recipient["recipientBank"]) 
#                     # await beneficiary.insert()
#                     # logging.info("Beneficiary details saved to database.")

#                     # Store beneficiary details in session
#                     # if beneficiary:
#                     #     session.beneficiary.append(beneficiary)
#                     #     await session.save()
#                     # logging.info("Beneficiary details saved to session.")

#                     if process_transfer['status'] == '00':
#                         result = f"Your transaction is successful"
#                     else:
#                         result = f"{process_transfer['message']}"
                        
#                     session.transfer_prompt_shown = False
#                     session.recipient_type = None  # Reset recipient type for next interaction
#                     await session.save()

#                 else:
#                     result = response['response_message']

#             elif recipient_type == "old":
#                 logging.info("Entered the beneficiary phase!")
#                 current_beneficiary = get_current_beneficiary_transfer_name(session, prompts.CURRENT_BENEFICIARY_TRANSFER_PROMPT)
#                 beneficiary_name = current_beneficiary['beneficiary_name']
#                 if beneficiary_name is None:
#                     result = current_beneficiary['response_message']
#                 else:
#                     current_recipient = Beneficiary.find({"phone_number": request.phone_number, "name": { "$regex": beneficiary_name, "$options": "i" }},
#                                                             {
#                                                                     "_id": 0,
#                                                                     "name": 1,
#                                                                     "account_number": 1,
#                                                                     "bank": 1
#                                                             }
#                                                         )
                        
#                     beneficiary_transfer = beneficiary_transfer_response(session, current_recipient, prompts.BENEFICIARY_TRANSFER_PROMPT)
#                     if beneficiary_transfer['is_request_completed']:

#                         # Extract transfer details to process transfer
#                         transfer_details = extract_transfer_details(session, prompts.TRANSFER_DETAILS_PROMPT)
#                         print("Transfer Details of beneficiary transfer process: ", transfer_details)

#                         process_transfer = VFDHelper.transfer_withdraw(session, transfer_details)
#                         print("Transfer endpoint output: ",process_transfer)

#                         if process_transfer['successful'] == True:
#                             result = f"Dear, your transaction is successful"
#                         elif process_transfer['successful'] == False:
#                             result = f"{process_transfer['message']}"
#                         else:
#                             result = f"Dear, {process_transfer['message']}"
#                         session.transfer_prompt_shown = False
#                         session.recipient_type = None
#                         await session.save()
#                     else:
#                         result = beneficiary_transfer['response_message']
#             else:
#                 if lastfive:
#                     beneficiaries = "\n".join(
#                         [f"-{b['name']} ({b['account_number']}, {b['bank']})" for b in lastfive]
#                     )
#                 print("Beneficiaries:", beneficiaries)
#                 result = f"Ok! You recently transferred to: {beneficiaries}. Would you like to transfer to one of your beneficiaries or a new recipient?"
#                 session.recipient_type = None  # Reset recipient type for next interaction
#                 await session.save()
            
#         print("Response after transfer:", result)
            
#     # if result:
#     message = Message(message=result, is_user=False)
#     session.chats.append(message)
#     await session.save()
#     logging.info("Bot response saved to session.")
#     whatsapp_msg = twilio_send_message(request.phone_number, result)
#     if whatsapp_msg:
#         return {"status": "sent", "sid": whatsapp_msg.sid}
#     else:
#         return {"status": "error", "detail": "Message not sent"}
#     #     return {'response' : result }
#     # else: 
#     #     return {'response' : "Error getting a response!!!" }
#     # send_message(request.phone_number, result)
#     # logging.info("Message sent to user via WhatsApp.")
#     # return ""
    
#     # res = await get_response(session)
#     # session.chats.append(Message(message=res["response_message"], is_user=False))
#     # await session.save()

# @app.post("/message")
# async def receive_whatsapp_message(
#     Body: str = Form(...),
#     From: str = Form(...)
# ):
#     phone_number = From.replace("whatsapp:", "")
#     user_message = Body

#     request_data = Request(phone_number=phone_number, message=user_message)

#     result = await send_message(request_data)  # ← your original logic

#     return ''


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="localhost", port=8001)

