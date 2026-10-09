from pydantic import BaseModel
from typing import Literal, Optional

class Claim(BaseModel):
    text: str
    status: Literal["published_fact", "inferred", "unknown"]
    source_url: Optional[str] = None
    quote: Optional[str] = None   # short supporting snippet from the page

class Contact(BaseModel):
    name: str
    title: str
    contact_info: Optional[str] = None
    source_url: str

class ResearchRecord(BaseModel):
    institution: str
    contacts: list[Contact]
    strategic_goals: list[Claim]
    tech_stack: list[Claim]
    regulatory_context: list[Claim]
    gaps: list[str]   # what we could not find

class Email(BaseModel):
    subject: str
    body: str

class CallScript(BaseModel):
    opener: str
    talking_points: list[str]
    discovery_questions: list[str]

class OutreachDraft(BaseModel):
    email: Email
    call: CallScript
    evidence_used: list[str] = []