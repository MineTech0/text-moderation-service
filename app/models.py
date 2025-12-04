from pydantic import BaseModel, HttpUrl
from typing import Optional, Literal

# API Request Models
class ModerationRequest(BaseModel):
    id: str
    text: str
    callback_url: HttpUrl

class ModerationResponse(BaseModel):
    status: Literal["queued"]
    id: str

# Callback / Internal Result Models
class ModerationReason(BaseModel):
    badword: bool
    toxicity_score: float
    model_label: str

class CallbackPayload(BaseModel):
    id: str
    text: Optional[str] = None
    decision: Literal["allow", "flag", "block"]
    reason: ModerationReason

