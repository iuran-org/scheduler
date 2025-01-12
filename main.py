from fastapi import FastAPI, HTTPException
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from pydantic import BaseModel
from datetime import datetime, timedelta
import json
import pytz
from dotenv import load_dotenv
import os
from typing import List, Optional
import re
import logging
import aiohttp
import asyncio
from aiobreaker import CircuitBreakerError, CircuitBreakerListener
from aiobreaker import CircuitBreaker
# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class CustomCircuitBreakerListener(CircuitBreakerListener):
    def before_call(self, cb, func, *args, **kwargs):
        logger.debug(f"CircuitBreaker about to call {func.__name__}")

    def after_call(self, cb, func, *args, **kwargs):
        logger.debug(f"CircuitBreaker finished calling {func.__name__}")

    def after_success(self, cb, func, *args, **kwargs):
        logger.info("CircuitBreaker call succeeded")

    def after_failure(self, cb, func, *args, **kwargs):
        logger.error("CircuitBreaker call failed")

    def state_change(self, cb, old_state, new_state):
        msg = f"CircuitBreaker state changed from {old_state} to {new_state}"
        if new_state == 'open':
            logger.error(msg)
        else:
            logger.info(msg)


# Setup Circuit Breaker
breaker = CircuitBreaker(
    # The maximum number of failures for the breaker
    fail_max=5,
    # The timeout to elapse for a breaker to close again
    timeout_duration=timedelta(seconds=60),
    # A list of CircuitBreakerListener
    listeners=[CustomCircuitBreakerListener()]
)


@breaker
async def make_request(url: str, payload: dict) -> dict:
    """
    Fungsi async yang dibungkus circuit breaker untuk melakukan HTTP request
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, timeout=10) as response:
            response.raise_for_status()
            return await response.json()


async def execute_callback_async(url: str, payload: dict):
    """
    Fungsi async yang digunakan oleh scheduler untuk menjalankan callback
    """
    try:
        logger.info(f"Executing callback to {url} with payload {payload}")
        result = await make_request(url, payload)
        logger.info(f"Callback executed successfully: {result}")

        # Log hasil eksekusi
        execution_result = {
            "timestamp": datetime.utcnow().isoformat(),
            "url": url,
            "payload": payload,
            "status": "SUCCESS",
            "response": str(result)[:1000]
        }
        logger.info(f"Execution result: {execution_result}")

        return result
    except CircuitBreakerError as e:
        logger.error(f"Circuit breaker is OPEN for {url}: {str(e)}")
        execution_result = {
            "timestamp": datetime.utcnow().isoformat(),
            "url": url,
            "payload": payload,
            "status": "CIRCUIT_OPEN",
            "error": str(e)
        }
        logger.error(f"Execution failed: {execution_result}")
        raise
    except aiohttp.ClientError as e:
        logger.error(f"Request failed for {url}: {str(e)}")
        execution_result = {
            "timestamp": datetime.utcnow().isoformat(),
            "url": url,
            "payload": payload,
            "status": "REQUEST_FAILED",
            "error": str(e)
        }
        logger.error(f"Execution failed: {execution_result}")
        raise
    except Exception as e:
        logger.error(
            f"Error in execute_callback_async: {str(e)}", exc_info=True)
        execution_result = {
            "timestamp": datetime.utcnow().isoformat(),
            "url": url,
            "payload": payload,
            "status": "UNEXPECTED_ERROR",
            "error": str(e)
        }
        logger.error(f"Execution failed: {execution_result}")
        raise


load_dotenv()

app = FastAPI()

DB_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

jobstores = {
    'default': SQLAlchemyJobStore(url=DB_URL)
}

scheduler = AsyncIOScheduler(
    jobstores=jobstores,
    timezone=pytz.UTC,
    job_defaults={
        'misfire_grace_time': int(os.getenv('MISFIRE_GRACE_TIME', 60 * 15)),
        'coalesce': True
    }
)
scheduler.start()


def parse_timezone(timezone_str: str) -> pytz.timezone:
    """
    Parse timezone string yang mendukung format:
    - Nama timezone (Asia/Jakarta)
    - GMT offset (GMT+7, GMT-7)
    - UTC offset (UTC+8, UTC-8)
    """
    # Cek format GMT/UTC offset
    offset_pattern = re.compile(r'^(GMT|UTC)([+-])(\d{1,2})$')
    match = offset_pattern.match(timezone_str.replace(" ", ""))

    if match:
        sign = 1 if match.group(2) == "+" else -1
        hours = int(match.group(3))
        offset = timedelta(hours=sign * hours)
        return pytz.FixedOffset(int(offset.total_seconds() / 60))

    # Jika bukan format offset, coba sebagai nama timezone
    try:
        return pytz.timezone(timezone_str)
    except pytz.exceptions.UnknownTimeZoneError:
        raise ValueError(f"Invalid timezone format: {timezone_str}")


class ScheduleRequest(BaseModel):
    schedule_time: datetime
    callback_url: str
    payload: dict
    timezone: str = "UTC"  # Bisa menggunakan format: "Asia/Jakarta", "GMT+7", "UTC+8"


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


@app.post("/jobs", response_model=ScheduleResponse)
async def create_job(request: ScheduleRequest):
    try:
        logger.debug(f"Received request: {request.dict()}")

        # Parse dan validasi timezone
        try:
            tz = parse_timezone(request.timezone)
            logger.debug(f"Parsed timezone: {tz}")
        except ValueError as e:
            logger.error(f"Timezone error: {str(e)}")
            raise HTTPException(
                status_code=400, detail=f"Timezone error: {str(e)}")

        # Konversi waktu ke timezone yang diminta
        try:
            if request.schedule_time.tzinfo is None:
                logger.debug(
                    "Schedule time has no timezone info, localizing...")
                schedule_time = tz.localize(request.schedule_time)
            else:
                logger.debug(
                    "Converting schedule time to requested timezone...")
                schedule_time = request.schedule_time.astimezone(tz)

            logger.debug(f"Final schedule time: {schedule_time}")

            # Validasi waktu harus di masa depan
            now = datetime.now(tz)
            logger.debug(f"Current time in timezone: {now}")

            if schedule_time <= now:
                logger.error(
                    f"Schedule time {schedule_time} is not in the future")
                raise HTTPException(
                    status_code=400,
                    detail="Schedule time must be in the future"
                )

            logger.debug("Adding job to scheduler...")
            job = scheduler.add_job(
                execute_callback_async,
                trigger=DateTrigger(run_date=schedule_time),
                args=[request.callback_url, request.payload],
                replace_existing=True,
                misfire_grace_time=None
            )
            logger.debug(f"Job added successfully with ID: {job.id}")

            response_data = {
                "job_id": job.id,
                "schedule_time": schedule_time,
                "callback_url": request.callback_url,
                "payload": request.payload,
                "timezone": request.timezone
            }
            logger.debug(f"Returning response: {response_data}")
            return response_data

        except Exception as e:
            logger.error(
                f"Error processing schedule time: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=400,
                detail=f"Error processing schedule time: {str(e)}"
            )
    except Exception as e:
        logger.error(f"Error creating job: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"Error creating job: {str(e)}"
        )


@app.get("/jobs", response_model=List[ScheduleResponse])
async def get_jobs(convert_to: str = "GMT+7"):
    try:
        jobs = scheduler.get_jobs()
        target_tz = parse_timezone(convert_to)

        job_list = []
        for job in jobs:
            if isinstance(job.trigger, DateTrigger):
                schedule_time = job.trigger.run_date.astimezone(target_tz)
            elif isinstance(job.trigger, IntervalTrigger):
                # Untuk interval job, gunakan next_fire_time
                schedule_time = job.next_run_time.astimezone(
                    target_tz) if job.next_run_time else None
                if schedule_time is None:
                    continue  # Skip jobs yang sudah selesai

            job_list.append({
                "job_id": job.id,
                "schedule_time": schedule_time,
                "callback_url": job.args[0],
                "payload": job.args[1],
                "timezone": convert_to
            })

        return job_list
    except Exception as e:
        logger.error(f"Error getting jobs: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"Error getting jobs: {str(e)}"
        )


@app.get("/jobs/{job_id}", response_model=ScheduleResponse)
async def get_job(job_id: str, convert_to: str = "GMT+7"):
    try:
        job = scheduler.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        target_tz = parse_timezone(convert_to)

        if isinstance(job.trigger, DateTrigger):
            schedule_time = job.trigger.run_date.astimezone(target_tz)
        elif isinstance(job.trigger, IntervalTrigger):
            schedule_time = job.next_run_time.astimezone(
                target_tz) if job.next_run_time else None
            if schedule_time is None:
                raise HTTPException(
                    status_code=404, detail="Job has no next run time")

        return {
            "job_id": job.id,
            "schedule_time": schedule_time,
            "callback_url": job.args[0],
            "payload": job.args[1],
            "timezone": convert_to
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timezone format: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error getting job: {str(e)}"
        )


@app.put("/jobs/{job_id}", response_model=ScheduleResponse)
async def update_job(job_id: str, request: ScheduleUpdate):
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    update_args = {}

    if request.schedule_time:
        # Parse timezone baru jika ada
        timezone_str = request.timezone or str(job.trigger.timezone)
        try:
            tz = parse_timezone(timezone_str)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        if request.schedule_time.tzinfo is None:
            schedule_time = tz.localize(request.schedule_time)
        else:
            schedule_time = request.schedule_time.astimezone(tz)

        update_args["trigger"] = DateTrigger(run_date=schedule_time)

    new_args = list(job.args)
    if request.callback_url:
        new_args[0] = request.callback_url
    if request.payload:
        new_args[1] = request.payload

    if new_args != job.args:
        update_args["args"] = new_args

    scheduler.modify_job(job_id, **update_args)

    updated_job = scheduler.get_job(job_id)
    return {
        "job_id": updated_job.id,
        "schedule_time": updated_job.trigger.run_date,
        "callback_url": updated_job.args[0],
        "payload": updated_job.args[1],
        "timezone": str(updated_job.trigger.timezone)
    }


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    scheduler.remove_job(job_id)
    return {"message": "Job deleted successfully"}


@app.post("/jobs/interval", response_model=ScheduleResponse)
async def create_interval_job(request: IntervalScheduleRequest):
    try:
        logger.debug(f"Received interval request: {request.dict()}")

        # Parse dan validasi timezone
        try:
            tz = parse_timezone(request.timezone)
            logger.debug(f"Parsed timezone: {tz}")
        except ValueError as e:
            logger.error(f"Timezone error: {str(e)}")
            raise HTTPException(
                status_code=400, detail=f"Timezone error: {str(e)}")

        # Konversi start_date dan end_date ke timezone yang diminta
        start_date = None
        if request.start_date:
            if request.start_date.tzinfo is None:
                start_date = tz.localize(request.start_date)
            else:
                start_date = request.start_date.astimezone(tz)

        end_date = None
        if request.end_date:
            if request.end_date.tzinfo is None:
                end_date = tz.localize(request.end_date)
            else:
                end_date = request.end_date.astimezone(tz)

        # Validasi interval
        total_seconds = (request.weeks * 7 * 24 * 3600 +
                         request.days * 24 * 3600 +
                         request.hours * 3600 +
                         request.minutes * 60 +
                         request.seconds)

        if total_seconds == 0:
            raise HTTPException(
                status_code=400,
                detail="At least one interval parameter must be greater than 0"
            )

        logger.debug("Adding interval job to scheduler...")
        job = scheduler.add_job(
            execute_callback_async,
            trigger=IntervalTrigger(
                weeks=request.weeks,
                days=request.days,
                hours=request.hours,
                minutes=request.minutes,
                seconds=request.seconds,
                start_date=start_date,
                end_date=end_date,
                timezone=tz,
                jitter=request.jitter
            ),
            args=[request.callback_url, request.payload],
            replace_existing=True,
            misfire_grace_time=None
        )
        logger.debug(f"Interval job added successfully with ID: {job.id}")

        # Untuk response, gunakan start_date sebagai schedule_time
        schedule_time = start_date if start_date else datetime.now(tz)

        response_data = {
            "job_id": job.id,
            "schedule_time": schedule_time,
            "callback_url": request.callback_url,
            "payload": request.payload,
            "timezone": request.timezone
        }
        logger.debug(f"Returning response: {response_data}")
        return response_data

    except Exception as e:
        logger.error(f"Error creating interval job: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"Error creating interval job: {str(e)}"
        )


@app.put("/jobs/interval/{job_id}", response_model=ScheduleResponse)
async def update_interval_job(job_id: str, request: IntervalScheduleUpdate):
    try:
        job = scheduler.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if not isinstance(job.trigger, IntervalTrigger):
            raise HTTPException(
                status_code=400, detail="This is not an interval job")

        # Parse timezone jika ada perubahan
        if request.timezone:
            try:
                tz = parse_timezone(request.timezone)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
        else:
            tz = job.trigger.timezone

        # Siapkan parameter untuk trigger baru
        trigger_args = {}

        # Ambil nilai existing jika tidak ada di request
        trigger_args['weeks'] = request.weeks if request.weeks is not None else job.trigger.interval.days // 7
        trigger_args['days'] = request.days if request.days is not None else job.trigger.interval.days % 7
        trigger_args['hours'] = request.hours if request.hours is not None else job.trigger.interval.seconds // 3600
        trigger_args['minutes'] = request.minutes if request.minutes is not None else (
            job.trigger.interval.seconds % 3600) // 60
        trigger_args['seconds'] = request.seconds if request.seconds is not None else job.trigger.interval.seconds % 60

        # Handle start_date dan end_date
        if request.start_date:
            if request.start_date.tzinfo is None:
                trigger_args['start_date'] = tz.localize(request.start_date)
            else:
                trigger_args['start_date'] = request.start_date.astimezone(tz)
        else:
            trigger_args['start_date'] = job.trigger.start_date

        if request.end_date:
            if request.end_date.tzinfo is None:
                trigger_args['end_date'] = tz.localize(request.end_date)
            else:
                trigger_args['end_date'] = request.end_date.astimezone(tz)
        else:
            trigger_args['end_date'] = job.trigger.end_date

        trigger_args['timezone'] = tz
        trigger_args['jitter'] = request.jitter if request.jitter is not None else job.trigger.jitter

        # Validasi interval
        total_seconds = (trigger_args['weeks'] * 7 * 24 * 3600 +
                         trigger_args['days'] * 24 * 3600 +
                         trigger_args['hours'] * 3600 +
                         trigger_args['minutes'] * 60 +
                         trigger_args['seconds'])

        if total_seconds == 0:
            raise HTTPException(
                status_code=400,
                detail="At least one interval parameter must be greater than 0"
            )

        # Update job arguments jika ada
        if request.callback_url or request.payload:
            new_args = list(job.args)
            if request.callback_url:
                new_args[0] = request.callback_url
            if request.payload:
                new_args[1] = request.payload
            scheduler.modify_job(job_id, args=new_args)

        # Update trigger
        scheduler.reschedule_job(
            job_id,
            trigger=IntervalTrigger(**trigger_args)
        )

        # Ambil job yang sudah diupdate
        updated_job = scheduler.get_job(job_id)
        schedule_time = updated_job.next_run_time.astimezone(
            tz) if updated_job.next_run_time else None

        return {
            "job_id": updated_job.id,
            "schedule_time": schedule_time,
            "callback_url": updated_job.args[0],
            "payload": updated_job.args[1],
            "timezone": request.timezone or str(tz)
        }

    except Exception as e:
        logger.error(f"Error updating interval job: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"Error updating interval job: {str(e)}"
        )


@app.post("/callback/test")
async def test_callback(payload: dict):
    """
    Endpoint dummy untuk testing callback
    """
    logger.info(f"Received callback with payload: {payload}")

    # Simulasi proses
    await asyncio.sleep(1)

    # Simulasi random error untuk testing circuit breaker
    import random
    if random.random() < 0.3:  # 30% chance of error
        logger.error("Simulated random error")
        raise HTTPException(status_code=500, detail="Simulated server error")

    return {
        "status": "success",
        "message": "Callback processed successfully",
        "received_at": datetime.now().isoformat(),
        "payload": payload
    }


@app.get("/health")
async def health_check():
    try:
        # Cek koneksi database
        jobs = scheduler.get_jobs()
        return {
            "status": "healthy",
            "database": "connected",
            "scheduler": "running",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Service unhealthy: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)
