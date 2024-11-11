# models.py
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime

class RawProject(BaseModel):
    id: str
    title: str
    description: str
    division: str
    owner_id: str
    metadata: Dict[str, Any]

class TransformedProject(BaseModel):
    id: str
    name: str
    created_at: datetime
    status: str
    owner: str
    metadata: Dict[str, Any]

class APIResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    timestamp: datetime