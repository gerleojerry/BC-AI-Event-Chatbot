import os
import logging
import prompts
import shutil
import aiohttp
from pprint import pprint
from dotenv import load_dotenv
from beanie import init_beanie
# from typing import Optional, Dict, Any
from qdrant_client import QdrantClient
from tempfile import NamedTemporaryFile
from fastapi import FastAPI, UploadFile, File
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client.models import VectorParams, Distance
from datetime import datetime, timedelta, time, date
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from models import Session, Message, User, RequestSchema, Event
from fastapi import FastAPI,Form,  Request, HTTPException, Query
from langchain_community.document_loaders import UnstructuredWordDocumentLoader
from helpers import get_conversations, get_response, get_user_info, get_event_info, get_stage, get_embedding, get_networking_user_info, build_beanie_query, ingest_document, answer_event_question, text_formater

load_dotenv()
# logging.basicConfig(level=logging.INFO,  format='%(asctime)s - %(levelname)s - %(message)s',  handlers=[logging.FileHandler('app.log', mode='w'), logging.StreamHandler()])

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
app = FastAPI()
scheduler = AsyncIOScheduler()
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def daily_countdown(): 
    print("Daily countdown job has begun!!")

    today = date.today()
    event_date = date(2026, 6, 10)
    difference = (event_date - today).days
    users = await User.find_all().to_list()

    for user in users: 
        user_name, phone_number = user.first_name, user.phone_number
        message = f"Hi {user_name}, 🚀 only {difference} days left! The BlueChip Data & AI Summit 3rd Edition is almost here!"
        print(message)
        whatsapp_msg = await send_text_message(phone_number, message)
        if whatsapp_msg:
            return {"success": True, "detail":"Message sent"}
        else:
            return {"success": False, "detail": "Message not sent"}
        

def check_event_date(): 
    today = date.today()
    event_date = date(2026, 6, 10)

    return today == event_date


async def survey_job(): 
    print("Survey job has begun!!")
    users = await User.find_all().to_list()

    for user in users: 
        user_name, phone_number = user.first_name, user.phone_number
        message = f"Hi {user_name}, we’d love your feedback on your experience with our chatbot and the event. Please take a moment to complete this short survey. https://docs.google.com/forms/d/e/1FAIpQLSe4MBtg4IgF5-GKS5yppk1QVJb8yVrGo_Ctok6yzlGN9BT-8Q/viewform"
        print(message)
        whatsapp_msg = await send_text_message(phone_number, message)
        if whatsapp_msg:
            return {"success": True, "detail":"Message sent"}
        else:
            return {"success": False, "detail": "Message not sent"}




async def job():
    print("Running job...")
    # now = datetime.now(timezone.utc)
    now = datetime.now()
    ten_minutes_later = now + timedelta(minutes=9)
    print(f"This the current time: {now}")
    # print(f"This is the time 10 minutes later: {ten_minutes_later}")
    docs = await Event.find(
    {
        "date_time": {
            "$gte": now,
            "$lte": ten_minutes_later
        }
    }
        ).to_list()
    
    print(f"This is the upcoming events in the next 10 minutes: {len(docs)}")
    for doc in docs: 
        event_name, event_time, event_room, phone_number = doc.name, doc.date_time, doc.room, doc.phone_number
        message = f"Reminder: You have the event '{event_name}' at {event_time.strftime('%H:%M')} in room {event_room} starting in less than 10 minutes. Don't miss it!"
        # request_data = RequestSchema(phone_number=phone_number, message=message)
        print(message)
        whatsapp_msg = await send_text_message(phone_number, message)
        if whatsapp_msg:
            return {"success": True, "detail":"Message sent"}
        else:
            return {"success": False, "detail": "Message not sent"}
        
    

async def init_db():
    collection_name = os.getenv("MONGO_DB_COLLECTION")
    mongo_string = os.getenv("MONGO_CONNECTION_STRING")
    client = AsyncIOMotorClient(mongo_string)
    await init_beanie(database=client[collection_name], document_models=[Session, User, Event])


def init_qdrant():
    qdrant = QdrantClient(url="http://qdrant:6333")
    collections = qdrant.get_collections().collections
    existing = [c.name for c in collections]

    if "document" not in existing:
        qdrant.create_collection(
            collection_name="document",
            vectors_config=VectorParams(
                size=3072,  # MUST match your embedding model
                distance=Distance.COSINE
            )
        )

    if "chunk" not in existing:
        qdrant.create_collection(
            collection_name="chunk",
            vectors_config=VectorParams(
                size=3072,
                distance=Distance.COSINE
            )
        )
    


def start_scheduler():
    scheduler.add_job(job, "interval", minutes=10)
    # Daily countdown
    scheduler.add_job(daily_countdown, trigger="date",run_date=datetime(2026, 6, 7, 8, 0))
    scheduler.add_job(daily_countdown, trigger="date",run_date=datetime(2026, 6, 8, 8, 0))
    scheduler.add_job(daily_countdown, trigger="date",run_date=datetime(2026, 6, 9, 8, 0))
    scheduler.add_job(daily_countdown, trigger="date",run_date=datetime(2026, 6, 10, 8, 0))
    # Survey
    scheduler.add_job(survey_job, trigger="date", run_date=datetime(2026, 6, 10, 20, 0))

    
    scheduler.start()

@app.on_event("startup")
async def start_db():
    await init_db()
    start_scheduler()
    init_qdrant()

@app.get("/health")
async def root():
    return {"response": "Seems good"}

@app.post("/create")
def create_user(): 
    return {"message": "User created successfully"}



# Send response to WhatsApp User
async def _post(data: dict):
        print(f"This is the data being sent to WhatsApp API: {data} from the post function.")
        headers = {
                    "Content-type": "application/json",
                    "Authorization": f"Bearer {os.getenv('WHATSAPP_ACCESS_TOKEN')}",
                    }
        
        async with aiohttp.ClientSession() as session:
            url = f"{os.getenv('BASE_URL')}/{os.getenv('API_VERSION')}/{os.getenv('PHONE_NUMBER_ID')}/messages"
            try:
                async with session.post(url, json=data,headers=headers) as resp:
                    if resp.status != 200:
                        return {"success":False, "message":"Error occurred"}
                    return {"success":True, "message":"Successful operation"}
            except Exception as e:
                logging.error(f"Error sending message: {e}")
                return {"success":False, "message": str(e)}
            

async def send_text_message(to:str, text: str, preview_url: bool = False):       
    print(f"Bot response: {text}")
    return await _post({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": preview_url, "body": text}
    })


async def send_message(request: RequestSchema):
    user = await User.find_one({'phone_number' : request.phone_number})

    if not user: 
        print("This is a new user")
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
            user = User(phone_number = request.phone_number, first_name = firstname, last_name = lastname, email = email, job = job, company = company_name, interest = interest, contact_share = contact_share, marketing_consent= marketing_consent)
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
        
        if request_type == "event":
            result = get_response(conversations , prompts.EVENT_BOT_PROMPT)
            print(result)
            pass

        elif request_type == "reminder_confirmation":
            events = get_event_info(conversations , prompts.EVENT_DATA_EXTRACTION)['event']
            print(events)
            if len(events) == 0: 
                result = "Sorry, Please make sure to include the name of the event, the time of the event and the room of the event in your message if you want to set a reminder for a particular event."
            elif len(events) == 1 and any(value == "" for value in events[0].values()):
                result = "Sorry, Please make sure to include the name of the event, the time of the event and the room of the event in your message if you want to set a reminder for a particular event."
            else:
                event_info = []
                for event in events:
                    hour, minute = map(int, event['time'].split(":"))
                    stored_time = time(hour, minute)
                    # fixed date: 10th June 2026
                    fixed_date = datetime(2026, 6, 10)
                    event_date = datetime.combine(fixed_date.date(), stored_time)
                    print(event_date)

                    event_info.append(Event(name = event['name'], date_time = event_date, room = event['room'], phone_number = request.phone_number))

                await Event.insert_many(event_info)

                events_data = "\n".join([f"{event['name']} at {event['time']} in room {event['room']}" for event in events])

                result =  f"A reminder has been set for you for the following event(s): {events_data} and you will receive the reminder 10 minutes before the event starts. Do you have any questions regarding the event?"

        elif request_type == "networking":
            usage = check_event_date()

            if usage is not True : 
                result = "This functionality is only available on the day of the event."
            else: 
            
                parsed = get_networking_user_info(request.message, prompts.NETWORK_USER_INFO)
                print(parsed)
                filters = build_beanie_query(parsed)
        

                if len(filters) == 1:
                    result = "Sorry, I couldn't get any valid attendee criteria from your request. Please try again with more specific information about the attendees you're looking for."
                else: 

                    filters["phone_number"] = {"$ne": request.phone_number}
                    print(filters)
                    users = await User.find(filters).limit(10).to_list()
                    attendees = [ f"{user.first_name} {user.last_name}, works as a {user.job} at {user.company}.Their contact email is {user.email}" for user in users if user.phone_number != request.phone_number] 
                
                    result = "Sorry, There aren't any attendee matching your criteria." if len(attendees) == 0 else "Here are some attendee(s) that match your criteria: " + "\n".join(attendees)

                    print(result)

        elif request_type == "event_subject":
            usage = check_event_date()
            if usage is not True : 
                result = "This functionality is only available on the day of the event."
            else: 
                result = await answer_event_question(request.message)
            print(result)
        
        elif request_type == "complimentary":
            result = "You're welcome! If you have any more questions or need further assistance, feel free to ask. Enjoy the event! 😊"
            print(result)
        
        else: 
            result = "Please can you clarify your request?"
    result= text_formater(result, prompts.RESPONSE_FORMATTER_PROMPT)
    message = Message(message=result, is_user=False)
    session.chats.append(message)
    await session.save()
    logging.info("Bot response saved to session.")
    # whatsapp_msg = await send_text_message(request.phone_number, result)
    # if whatsapp_msg:
    #     return {"success": True, "detail":"Message sent"}
    # else:
    #     return {"success": False, "detail": "Message not sent"}
    return {'response' : result }['response']


@app.post("/message")
async def receive_whatsapp_message(
    From: str = Form(...),
    Body: str = Form(...)
):
    phone_number = From.replace("whatsapp:", "")
    user_message = Body
    request_data = RequestSchema(phone_number=phone_number, message=user_message)
    result = await send_message(request_data)  # ← your original logic
    return result


@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...)
):   
    
    try:
        with NamedTemporaryFile(delete=False, suffix=file.filename) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = temp_file.name

        if file.filename.endswith(".docx"):
            loader = UnstructuredWordDocumentLoader(temp_path)

        else:
            return {"error": "Unsupported file type"}

        print("This is the file name: ", file.filename)
        data = loader.load()[0].page_content 
        await ingest_document(data, f"{file.filename}")

        # Select all the user that registered for the event. 

        # Loop through all the users and send them a message. 
        filters = {'name' : file.filename}

        users = await Event.find(filters).to_list()
        for user in users: 
            message = f"Knowledge based for the session '{file.filename}' is ready and shared to you because you registered for it. Feel free to ask any question regarding the session and I will be happy to assist you."
            await send_text_message(user.phone_number, message)
        


        return {"response": "Document ingested and shared to the interested parties successfully!!!"}


    except Exception as e:
        logging.error(f"Error ingesting document: {e}")
        return {"response": "Failed to ingest document!!!"}
    
    
# Health check
@app.get("/")
async def home():
    return {"message": "API is up"}



# Webhook verification
@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Forbidden")




@app.post("/webhook")
async def whatsapp_callback(request: Request):
    print("The webhoo has been called.")
    payload = await request.json()  # parse JSON body into dict
    pprint(f"{payload=}")

    if payload.get("object") != "whatsapp_business_account":
        return {"error": "Invalid object"}

    result = "Sorry, I can only process text messages for now."
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") == "messages":
                for msg in change.get("value", {}).get("messages", []):
                    if msg.get("type") == "text":
                        print(
                            f"{msg.get('from')} sent you a message!\n"
                            f"The content of the message reads: {msg.get('text', {}).get('body')}"
                        )
                        # await process_message(
                        #     msg.get("from"),
                        #     msg.get("text", {}).get("body", "")
                        # )
                        request_data = RequestSchema(phone_number=msg.get("from"), message = msg.get("text", {}).get("body", ""))
                        result = await send_message(request_data)  # ← your original logic

   
                   
                    

    return {"success": True, 'response': result, "status": "Message received"}




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)