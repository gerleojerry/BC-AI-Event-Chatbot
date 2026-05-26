from beanie import Document, Update, Save, SaveChanges, Replace, Insert, before_event
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
from typing import Any, List

def get_utc_now():
    return datetime.now(timezone.utc)

class BaseDocument(Document):
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)

    @before_event(Insert)
    def set_created_at(self) -> None:
        self.created_at = get_utc_now()

    @before_event(Update, Save, SaveChanges, Replace)
    def set_updated_at(self) -> None:
        self.updated_at = get_utc_now()




class Message(BaseDocument):
    message: str
    is_user: bool

    

class Session(BaseDocument):
    phone_number: str
    chats: List[Message] = []
    is_active: bool = True
    does_user_exist: bool = False
    chat_phase: str = 'default'
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    address: Optional[str] = None

    class Settings:
        name = "sessions"

class User(BaseDocument):
    phone_number: str
    first_name: str 
    last_name: str
    interest: str
    job: str
    company: str
    contact_share: bool
    email: str = None
    marketing_consent: bool = False
    embedded_interest : Optional[List[float]] = None
    
    class Settings:
        name = "users"


class RequestSchema(BaseModel):
    phone_number: str
    message: str


class Event(BaseDocument):
    name: str
    date_time: datetime
    room: str
    phone_number: str
    
    class Settings:
        name = "events"
        indexes = ["date_time"]



class RagDocument(BaseDocument):
    document_id: str
    content: str
    embedding: List[float]

    class Settings:
        name = "documents"


class RagChunk(BaseDocument):
    document_id: str
    chunk_index: int
    content: str
    embedding: List[float]

    class Settings:
        name = "chunks"
        indexes = ["document_id"]