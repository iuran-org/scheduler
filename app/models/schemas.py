from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict


class ScheduleRequest(BaseModel):
    schedule_time: datetime
    callback_url: str
    payload: dict
    timezone: str = "UTC"


class ScheduleResponse(BaseModel):
    job_id: str
    schedule_time: datetime
    callback_url: str
    payload: dict
    timezone: str


class ScheduleUpdate(BaseModel):
    schedule_time: Optional[datetime] = None
    callback_url: Optional[str] = None
    payload: Optional[dict] = None
    timezone: Optional[str] = None


class IntervalScheduleRequest(BaseModel):
    weeks: Optional[int] = 0
    days: Optional[int] = 0
    hours: Optional[int] = 0
    minutes: Optional[int] = 0
    seconds: Optional[int] = 0
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    timezone: str = "UTC"
    callback_url: str
    payload: dict
    jitter: Optional[int] = None


class IntervalScheduleUpdate(BaseModel):
    weeks: Optional[int] = None
    days: Optional[int] = None
    hours: Optional[int] = None
    minutes: Optional[int] = None
    seconds: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    timezone: Optional[str] = None
    callback_url: Optional[str] = None
    payload: Optional[dict] = None
    jitter: Optional[int] = None
