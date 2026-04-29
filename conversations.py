import os 
import logging
from beanie import Document
from typing import Type, List, Any
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from telegram.ext import  ContextTypes




load_dotenv()

logging.basicConfig(level=logging.INFO,  format='%(asctime)s - %(levelname)s - %(message)s',  handlers=[logging.FileHandler('app.log', mode='w'), logging.StreamHandler()])

os.environ["OPENAI_API_KEY"] =  os.getenv("OPENAI_API_KEY")

# model_name = "gpt-4o-mini"
model_name = "gpt-5.4-nano-2026-03-17"
temperature = 0.1

model = ChatOpenAI(model=model_name, temperature= temperature)

class DataExactraction(BaseModel):
    
        """user details extraction from conversation."""
        first_name: str = Field(description="The user's first name ")
        last_name: str = Field(description="The user's last name ")
        email : str = Field(description = "The user's email")
        job: str = Field(description="The users job")
        company_name: str = Field(description="The user's company name")
        interest : str = Field(description = "The User's interest"),
        marketing_consent: bool = Field(description="Whether the user consents to share their information for marketing purposes or not, the value should be either True or False")
        contact_share: str = Field(description="Whether the user wants to share their contact information with other attendees or not, the value should be either True or False")



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
    chain = messages | model
    response = chain.invoke({})  
    logging.info(f"Response Generated!")
        
    return response.content




def get_stage(conversations, stage_prompt) : 

    stage = PromptTemplate.from_template(stage_prompt)
    stage_chain = stage | model

    response = stage_chain.invoke({"message" : conversations }).content

    return response


def get_user_info(conversations, extraction_prompt) : 

    data_parser = JsonOutputParser(pydantic_object=DataExactraction)
    extraction_template = PromptTemplate.from_template(extraction_prompt)
    extraction_pipeline = extraction_template | model | data_parser
    response = extraction_pipeline.invoke({"document": conversations })
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
    phone_number: str,
    embedding_field: str = "embedded_interest",
    index_name: str = "user_vector_index",
    limit: int = 5,
    num_candidates: int = 1000
) -> List[Any]:


    source_doc = await document_model.find_one({"phone_number": phone_number})


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



# async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):

#     user = update.effective_user
#     user_id = str(user.id)
#     username = user.username
#     first_name = user.first_name
#     user_text = update.message.text 
#     user_text = str(user_text)