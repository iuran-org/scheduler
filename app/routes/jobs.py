from fastapi import APIRouter, HTTPException
from typing import List
from datetime import datetime
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.models.schemas import (
    ScheduleRequest, ScheduleResponse, ScheduleUpdate,
    IntervalScheduleRequest, IntervalScheduleUpdate
)
from app.utils.timezone import parse_timezone
from app.utils.circuit_breaker import execute_callback_async
from app.config.settings import scheduler

router = APIRouter()


@router.post("/jobs", response_model=ScheduleResponse)
async def create_job(request: ScheduleRequest):
    try:
        tz = parse_timezone(request.timezone)

        if request.schedule_time.tzinfo is None:
            schedule_time = tz.localize(request.schedule_time)
        else:
            schedule_time = request.schedule_time.astimezone(tz)

        now = datetime.now(tz)
        if schedule_time <= now:
            raise HTTPException(
                status_code=400,
                detail="Schedule time must be in the future"
            )

        trigger = DateTrigger(
            run_date=schedule_time,
            timezone=tz
        )

        job = scheduler.add_job(
            execute_callback_async,
            trigger=trigger,
            args=[request.callback_url, request.payload]
        )

        return {
            "job_id": job.id,
            "schedule_time": schedule_time,
            "callback_url": request.callback_url,
            "payload": request.payload,
            "timezone": request.timezone
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs", response_model=List[ScheduleResponse])
async def get_jobs(convert_to: str = "GMT+7"):
    try:
        target_tz = parse_timezone(convert_to)
        jobs = scheduler.get_jobs()

        job_list = []
        for job in jobs:
            next_run_time = job.next_run_time
            if next_run_time:
                next_run_time = next_run_time.astimezone(target_tz)

            job_list.append({
                "job_id": job.id,
                "schedule_time": next_run_time,
                "callback_url": job.args[0],
                "payload": job.args[1],
                "timezone": convert_to
            })

        return job_list
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}", response_model=ScheduleResponse)
async def get_job(job_id: str, convert_to: str = "GMT+7"):
    try:
        target_tz = parse_timezone(convert_to)
        job = scheduler.get_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        next_run_time = job.next_run_time
        if next_run_time:
            next_run_time = next_run_time.astimezone(target_tz)

        return {
            "job_id": job.id,
            "schedule_time": next_run_time,
            "callback_url": job.args[0],
            "payload": job.args[1],
            "timezone": convert_to
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/jobs/{job_id}", response_model=ScheduleResponse)
async def update_job(job_id: str, request: ScheduleUpdate):
    try:
        job = scheduler.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        job_args = list(job.args)
        job_kwargs = dict(job.kwargs)

        if request.callback_url is not None:
            job_args[0] = request.callback_url

        if request.payload is not None:
            job_args[1] = request.payload

        if request.schedule_time is not None or request.timezone is not None:
            tz = parse_timezone(request.timezone or job.trigger.timezone.zone)

            if request.schedule_time:
                if request.schedule_time.tzinfo is None:
                    schedule_time = tz.localize(request.schedule_time)
                else:
                    schedule_time = request.schedule_time.astimezone(tz)

                now = datetime.now(tz)
                if schedule_time <= now:
                    raise HTTPException(
                        status_code=400,
                        detail="Schedule time must be in the future"
                    )
            else:
                schedule_time = job.next_run_time

            trigger = DateTrigger(
                run_date=schedule_time,
                timezone=tz
            )

            scheduler.reschedule_job(
                job_id,
                trigger=trigger
            )

        scheduler.modify_job(
            job_id,
            args=job_args,
            kwargs=job_kwargs
        )

        updated_job = scheduler.get_job(job_id)
        return {
            "job_id": updated_job.id,
            "schedule_time": updated_job.next_run_time,
            "callback_url": updated_job.args[0],
            "payload": updated_job.args[1],
            "timezone": request.timezone or job.trigger.timezone.zone
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    try:
        job = scheduler.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        scheduler.remove_job(job_id)
        return {"message": "Job deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/interval", response_model=ScheduleResponse)
async def create_interval_job(request: IntervalScheduleRequest):
    try:
        tz = parse_timezone(request.timezone)

        if request.start_date and request.start_date.tzinfo is None:
            start_date = tz.localize(request.start_date)
        else:
            start_date = request.start_date

        if request.end_date and request.end_date.tzinfo is None:
            end_date = tz.localize(request.end_date)
        else:
            end_date = request.end_date

        if start_date:
            now = datetime.now(tz)
            if start_date <= now:
                raise HTTPException(
                    status_code=400,
                    detail="Start date must be in the future"
                )

        trigger = IntervalTrigger(
            weeks=request.weeks,
            days=request.days,
            hours=request.hours,
            minutes=request.minutes,
            seconds=request.seconds,
            start_date=start_date,
            end_date=end_date,
            timezone=tz,
            jitter=request.jitter
        )

        job = scheduler.add_job(
            execute_callback_async,
            trigger=trigger,
            args=[request.callback_url, request.payload]
        )

        return {
            "job_id": job.id,
            "schedule_time": job.next_run_time,
            "callback_url": request.callback_url,
            "payload": request.payload,
            "timezone": request.timezone
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/jobs/interval/{job_id}", response_model=ScheduleResponse)
async def update_interval_job(job_id: str, request: IntervalScheduleUpdate):
    try:
        job = scheduler.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if not isinstance(job.trigger, IntervalTrigger):
            raise HTTPException(
                status_code=400,
                detail="This job is not an interval job"
            )

        job_args = list(job.args)
        job_kwargs = dict(job.kwargs)

        if request.callback_url is not None:
            job_args[0] = request.callback_url

        if request.payload is not None:
            job_args[1] = request.payload

        trigger_args = {}

        if request.timezone is not None:
            try:
                trigger_args['timezone'] = parse_timezone(request.timezone)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
        else:
            trigger_args['timezone'] = job.trigger.timezone

        if request.start_date is not None:
            if request.start_date.tzinfo is None:
                start_date = trigger_args['timezone'].localize(
                    request.start_date)
            else:
                start_date = request.start_date.astimezone(
                    trigger_args['timezone'])

            now = datetime.now(trigger_args['timezone'])
            if start_date <= now:
                raise HTTPException(
                    status_code=400,
                    detail="Start date must be in the future"
                )
            trigger_args['start_date'] = start_date

        if request.end_date is not None:
            if request.end_date.tzinfo is None:
                end_date = trigger_args['timezone'].localize(request.end_date)
            else:
                end_date = request.end_date.astimezone(
                    trigger_args['timezone'])
            trigger_args['end_date'] = end_date

        interval_args = ['weeks', 'days', 'hours',
                         'minutes', 'seconds', 'jitter']
        for arg in interval_args:
            value = getattr(request, arg)
            if value is not None:
                trigger_args[arg] = value
            else:
                trigger_args[arg] = getattr(job.trigger, arg)

        trigger = IntervalTrigger(**trigger_args)

        scheduler.reschedule_job(
            job_id,
            trigger=trigger
        )

        scheduler.modify_job(
            job_id,
            args=job_args,
            kwargs=job_kwargs
        )

        updated_job = scheduler.get_job(job_id)
        return {
            "job_id": updated_job.id,
            "schedule_time": updated_job.next_run_time,
            "callback_url": updated_job.args[0],
            "payload": updated_job.args[1],
            "timezone": request.timezone or job.trigger.timezone.zone
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
