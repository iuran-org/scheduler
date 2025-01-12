from fastapi import FastAPI
import logging
import asyncio
from app.routes import jobs, test
from app.config.settings import scheduler

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(title="Scheduler Service API", version="1.0.0",
              description="Scheduler Service API",
              openapi_url="/openapi.json",
              docs_url="/docs",
              redoc_url="/redoc")

app.include_router(jobs.router, tags=["jobs"])
app.include_router(test.router, tags=["test"])


@app.on_event("startup")
async def startup_event():
    scheduler.start()
    logger.info("Scheduler started")


@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()
    logger.info("Scheduler shutdown")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)
