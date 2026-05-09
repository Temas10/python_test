from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class DataPayload(BaseModel):
    x: float
    y: float
    z: float

class UserCreate(BaseModel):
    name: str

class DeviceCreate(BaseModel):
    id: int

class AnalyticsParams(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None