import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Form
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from models import Session, Message, User, Request 
import prompts
from conversations import get_conversations, get_response, get_user_info, get_stage, get_embedding, find_similar_documents


load_dotenv()
logging.basicConfig(level=logging.INFO,  format='%(asctime)s - %(levelname)s - %(message)s',  handlers=[logging.FileHandler('app.log', mode='w'), logging.StreamHandler()])


app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# @app.on_event("startup")
# async def start_db():
#     await init_db()

@app.get("/health")
async def root():
    return {"response": "Seems good"}


@app.post("/create")
def create_user(): 
    pass



async def send_message(request: Request):

    collection_name = 'sparkle'
    mongo_string = os.getenv("MONGO_CONNECTION_STRING")

   
    client = AsyncIOMotorClient(mongo_string)

    await init_beanie(database=client[collection_name], document_models=[Session, User])

    user = await User.find_one({'phone_number' : request.phone_number})

    if not user: 
        print("THis is a new user")
        session = await Session.find_one({"phone_number": request.phone_number})

        if not session: 
            session =  Session(phone_number = request.phone_number)

        message = Message(message = request.message , is_user = True)

        session.chats.append(message)
        await session.save()
        logging.info("User Message saved to the session.")

        conversations = get_conversations(session)
        result = get_response(conversations , prompts.ONBOARDING_PROMPTS)

        stage_detector = get_stage(conversations, prompts.ONBOARDING_STAGE_DETECTOR)
        print("This is the conversation type: ", stage_detector)
       
        if stage_detector == "confirmation":
            customer_info = get_user_info(conversations, prompts.ONBOARDING_DATA_EXTRACTION)
            print("This is the extracted information: ", customer_info)

            firstname, lastname, email, job, company_name, interest, contact_share, marketing_consent = customer_info.values()
            embedded_interest = get_embedding(interest)
            print(firstname, lastname, email, job, company_name, interest, contact_share, marketing_consent)

            user = User(phone_number = request.phone_number, first_name = firstname, last_name = lastname, email = email, job = job, company = company_name, interest = interest, contact_share = contact_share, marketing_consent= marketing_consent, embedded_interest = embedded_interest)
            await user.insert()
            logging.info("New User registration process successful.")

    
    else:
        print("This is not a new customer.")
        session = await Session.find_one({"phone_number": request.phone_number})
        message = Message(message = request.message, is_user = True)
        
        if session:
            session.chats.append(message)
            await session.save()
            logging.info("User message saved to session")

        else:
            session = Session(phone_number=request.phone_number)
            session.chats = [message]
            await session.insert()
            logging.info("New session created and user message saved.")

        conversations = get_conversations(session)
        request_type = get_response(conversations, prompts.CONVERSATION_STAGE_DETECTOR)
        print("This is the conversation type: ", request_type)

        

        if request_type == "networking":
            similar_attendees = await find_similar_documents(document_model =user, phone_number = request.phone_number)
            print("These are the similar attendees: ", similar_attendees)

            similar_attendees = str(similar_attendees)



            result = get_response(similar_attendees, prompts.NETWORKING_RESPONSE_PRETTIFIER)


            # for att in similar_attendees: 
                # print(att.first_name, att.last_name, att.email, att.job, att.interest)
        else:
            result = get_response(conversations , prompts.GENERAL_BOT_PROMPT)
            print(result)
        
        

    message = Message(message=result, is_user=False)
    session.chats.append(message)
    await session.save()
    logging.info("Bot response saved to session.")

    return {'response' : result }['response']


@app.post("/message")
async def receive_whatsapp_message(
    From: str = Form(...),
    Body: str = Form(...)
):
    phone_number = From.replace("whatsapp:", "")
    user_message = Body

    request_data = Request(phone_number=phone_number, message=user_message)

    result = await send_message(request_data)  # ← your original logic

    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8001)

