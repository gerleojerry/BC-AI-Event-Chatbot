import os 
import logging
import numpy as np
from uuid import uuid4
from beanie import Document
from dotenv import load_dotenv
from beanie import init_beanie
from typing import Type, List, Any
from langchain_chroma import Chroma
from langchain.schema import Document
from pydantic import BaseModel, Field
from telegram.ext import  ContextTypes
from langchain_openai import ChatOpenAI
from models import RagChunk, RagDocument
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone, timedelta, time
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate

load_dotenv()

logging.basicConfig(level=logging.INFO,  format='%(asctime)s - %(levelname)s - %(message)s',  handlers=[logging.FileHandler('app.log', mode='w'), logging.StreamHandler()])

os.environ["OPENAI_API_KEY"] =  os.getenv("OPENAI_API_KEY")

COLLECTION_NAME = 'bluechip'
MONGO_STRING = os.getenv("MONGO_CONNECTION_STRING")  

PERSIST_DIR = "./chroma_db"
DOCUMENT_COLLECTION = "document_index"
CHUNK_COLLECTION = "chunk_index"

EMBED_MODEL = "text-embedding-3-large"

NANO_MODEL_NAME = "gpt-5.4-nano-2026-03-17"
MODEL_NAME = "gpt-5.4-mini-2026-03-17"
LARGE_MODEL_NAME = "gpt-5.4-2026-03-05"
temperature = 0

MODEL = ChatOpenAI(model=MODEL_NAME, temperature= temperature)
NANO_MODEL = ChatOpenAI(model=NANO_MODEL_NAME, temperature= temperature)
LARGE_MODEL = ChatOpenAI(model=LARGE_MODEL_NAME, temperature= temperature)

TOP_K_DOCS = 1       
TOP_K_CHUNKS = 3

embeddings = OpenAIEmbeddings(model=EMBED_MODEL)

# Better chunking
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)

class DataExactraction(BaseModel):
        """user details extraction from conversation."""
        first_name: str = Field(description="The user's first name ")
        last_name: str = Field(description="The user's last name ")
        email : str = Field(description = "The user's email")
        job: str = Field(description="The users job")
        company_name: str = Field(description="The user's company name")
        interest : str = Field(description = "The User's interest"),
        marketing_consent: bool = Field(description="Whether the user consents to share their information for marketing purposes or not, the value should be either True or False")
        contact_share: bool = Field(description="Whether the user wants to share their contact information with other attendees or not, the value should be either True or False")


class AttendeeData(BaseModel):
        """Attendees details extraction from conversation for networking."""
        first_name: str = Field(description="The attendee's first name ")
        last_name: str = Field(description="The attendee's last name ")
        email : str = Field(description = "The attendee's email")
        job: str = Field(description="The attendee's job")
        company_name: str = Field(description="The name of the company the attendee works for.")


class EventItem(BaseModel):
        """Generate the event details from a conversation."""
        name: str = Field(description="The name of the event.")
        time: str = Field(description="The time of the event.")
        room : str = Field(description = "The room where the event will take place.")

class Event(BaseModel): 
    event: List[EventItem]
       


def get_conversations(session): 
    logging.info("Getting the historical conversatoin")
    prompt = ""
    for con in session.chats : 
        if con.is_user: 
            prompt = prompt + f"user: {con.message} "

        else: 
            prompt = prompt + f"Bot: {con.message} "

    logging.info(f"Prompt generated!!")

    return prompt



def get_response(conversation: str, onboarding_prompt: str): 
             
    messages = ChatPromptTemplate.from_messages( 
        [
            SystemMessage(onboarding_prompt),
            HumanMessage(conversation )
        ]
     )     
    chain = messages | MODEL
    response = chain.invoke({})  
    logging.info(f"Response Generated!")
        
    return response.content




def get_stage(conversations, stage_prompt) : 

    stage = PromptTemplate.from_template(stage_prompt)
    stage_chain = stage | MODEL

    response = stage_chain.invoke({"message" : conversations }).content

    return response


def get_user_info(conversations, extraction_prompt) : 

    data_parser = JsonOutputParser(pydantic_object=DataExactraction)
    extraction_template = PromptTemplate.from_template(extraction_prompt)
    extraction_pipeline = extraction_template | NANO_MODEL | data_parser
    response = extraction_pipeline.invoke({"document": conversations })
    return response


def get_event_info(conversations, extraction_prompt) : 
    data_parser = JsonOutputParser(pydantic_object=Event)
    extraction_template = PromptTemplate.from_template(extraction_prompt)
    extraction_pipeline = extraction_template | MODEL | data_parser
    response = extraction_pipeline.invoke({"document": conversations, 'format_instruction' : data_parser.get_format_instructions()})
    return response


def get_networking_user_info(query, extraction_prompt) : 
    data_parser = JsonOutputParser(pydantic_object=AttendeeData)
    extraction_template = PromptTemplate.from_template(extraction_prompt)
    extraction_pipeline = extraction_template | MODEL | data_parser
    response = extraction_pipeline.invoke({"document": query })
    return response


large_embedding = "text-embedding-3-large"
small_embedding = "text-embedding-3-small"

def get_embedding(text: str) -> list[float]:
    
    if not text or not text.strip():
        raise ValueError("Input text cannot be empty")

    embeddings = OpenAIEmbeddings(model=large_embedding)
    vector = embeddings.embed_query(text)

    return vector


async def find_similar_documents(
    document_model: Type[Document],
    attribute_name : str,
    phone_number: str,
    embedding_field: str = "embedded_interest",
    index_name: str = "user_vector_index",
    limit: int = 5,
    num_candidates: int = 1000
) -> List[Any]:


    source_doc = await document_model.find_one({f"{attribute_name}": phone_number})


    if not source_doc:
        raise ValueError("Document not found")

    if not hasattr(source_doc, embedding_field):
        raise ValueError(f"Missing '{embedding_field}' field in document")

    query_vector = getattr(source_doc, embedding_field)
    # Step 2: Aggregation pipeline
    pipeline = [
        {
            "$vectorSearch": {
                "index": index_name,
                "path": embedding_field,
                "queryVector": query_vector,
                "numCandidates": num_candidates,
                "limit": limit
            }
        },
        {
            "$match": {
                "phone_number": {"$ne": phone_number}, 
                "contact_share" : True
            }
        },
        {
            "$project": {
                "first_name": 1,
                "last_name": 1,
                "email": 1,
                "interest": 1,
                "phone_number": 1,
                "score": {"$meta": "vectorSearchScore"}
            }
        }
    ]

    collection = document_model.get_motor_collection()
    cursor = collection.aggregate(pipeline)

    results = []
    async for doc in cursor:
        results.append(doc)

    print(results)
    return results


def build_beanie_query(json_data):
    json_data = {} if (isinstance(json_data, list) and len(json_data) == 0) else json_data
    json_data = json_data[0] if isinstance(json_data, list) else json_data
    filters = {}
    filters["contact_share"] =  True
    if json_data.get("first_name"):
        filters["first_name"] = {"$regex": json_data["first_name"], "$options": "i"}

    if json_data.get("last_name"):
        filters["last_name"] = {"$regex": json_data["last_name"], "$options": "i"}

    if json_data.get("interest"):
        filters["interest"] = {"$regex": json_data["interest"], "$options": "i"}

    if json_data.get("job"):
        filters["job"] = {"$regex": json_data["job"], "$options": "i"}

    if json_data.get("company_name"):
        filters["company"] = {"$regex": json_data["company_name"], "$options": "i"}

    return filters


   




# ---- USING BEANIE FOR VECTOR SEARCH (EXPERIMENTAL) ----



async def init_db():
    CLIENT = AsyncIOMotorClient(MONGO_STRING)
    await init_beanie(database=CLIENT[COLLECTION_NAME], document_models=[RagDocument, RagChunk])


def embed_text(text: str) -> List[float]:
    return embeddings.embed_query(text)



async def check_doc_exists(doc_id: str) -> bool:

    print(f"[CHECKING DOCUMENT EXISTENCE] Checking if document exists for id: {doc_id}")

    existing = await RagDocument.find_one(
        {'document_id' : doc_id}
    )
    
    documents = await RagDocument.find_all().to_list()
    count_exist = len(documents)
    print(f"[CHECKING DOCUMENT COUNT] Found {count_exist} documents with id: {doc_id}") 


    return existing is not None


async def ingest_document(
    text: str,
    doc_id: str
):
    """
    Ingest into:
    - document collection
    - chunk collection
    """
    await init_db()
    print(f"[INGESTION PROCESS] Checking if document exists for id: {doc_id}")

    doc_exists = await check_doc_exists(doc_id)   

    if doc_exists:
        print(f"[SKIPPED] {doc_id} already exists.")
        return

    print("[INGESTING] The Document does not exist.")


    doc_embedding = embed_text(text)

    doc = RagDocument(
        document_id=doc_id,
        content=text,
        embedding=doc_embedding
    )

    await doc.insert()


    chunks = splitter.split_text(text)

    chunk_docs = []

    for i, chunk in enumerate(chunks):

        chunk_embedding = embed_text(chunk)

        chunk_doc = RagChunk(
            document_id=doc_id,
            chunk_index=i,
            content=chunk,
            embedding=chunk_embedding
        )

        chunk_docs.append(chunk_doc)

    if chunk_docs:
        await RagChunk.insert_many(chunk_docs)

    print(f"[INGESTED] {doc_id} with {len(chunks)} chunks")


async def route_to_documents(
    query: str,
    k: int = TOP_K_DOCS
):

    query_embedding = embed_text(query)

    pipeline = [
        {
            "$vectorSearch": {
                "index": "document_index",
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": 100,
                "limit": k
            }
        },
        {
            "$project": {
                "_id": 0,
                "document_id": 1,
                "score": {
                    "$meta": "vectorSearchScore"
                }
            }
        }
    ]

    results = await RagDocument.aggregate(
        pipeline
    ).to_list()

    doc_ids = [
        doc["document_id"]
        for doc in results
    ]

    print(f"[ROUTER] Selected docs: {doc_ids}")

    return doc_ids

async def retrieve_chunks(
    query: str,
    doc_ids: List[str],
    k: int = TOP_K_CHUNKS
):

    query_embedding = embed_text(query)

    all_chunks = []

    for doc_id in doc_ids:

        pipeline = [
            {
                "$vectorSearch": {
                    "index": "chunk_index",
                    "path": "embedding",
                    "queryVector": query_embedding,
                    "numCandidates": 100,
                    "limit": k,
                    "filter": {
                        "document_id": doc_id
                    }
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "content": 1,
                    "score": {
                        "$meta": "vectorSearchScore"
                    }
                }
            }
        ]

        results = await RagChunk.aggregate(
            pipeline
        ).to_list()

        all_chunks.extend(
            [r["content"] for r in results]
        )

    return all_chunks


def generate_answer(
    query: str,
    context_chunks: List[str]
) -> str:

    context = "\n\n".join(context_chunks)

    prompt = f"""
    You are a precise assistant.

    Answer ONLY using the provided context.

    If the answer is not in the context,
    say "Please can you add more context to the question.".

    Question:
    {query}

    Context:
    {context}

    Answer:
    """

    response = MODEL.invoke(prompt)

    return response.content.strip()



async def answer_event_question(
    query: str
) -> str:

    await init_db()
    doc_ids = await route_to_documents(query)

    chunks = await retrieve_chunks(
        query,
        doc_ids
    )

    answer = generate_answer(
        query,
        chunks
    )

    return answer