import os
from dotenv import load_dotenv
import pytz
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()

DB_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

JOBSTORES = {
    'default': SQLAlchemyJobStore(url=DB_URL)
}

SCHEDULER_CONFIG = {
    'jobstores': JOBSTORES,
    'timezone': pytz.UTC,
    'job_defaults': {
        'misfire_grace_time': int(os.getenv('MISFIRE_GRACE_TIME', 60 * 15)),
        'coalesce': True
    }
}

scheduler = AsyncIOScheduler(**SCHEDULER_CONFIG)
