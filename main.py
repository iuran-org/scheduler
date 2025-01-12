from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
import logging
import asyncio
from app.routes import jobs, test
from app.config.settings import scheduler
import os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

security = HTTPBasic()


def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = os.getenv("API_DOCS_USERNAME", "admin")
    correct_password = os.getenv("API_DOCS_PASSWORD", "secret")
    is_correct_username = secrets.compare_digest(
        credentials.username.encode("utf8"), correct_username.encode("utf8"))
    is_correct_password = secrets.compare_digest(
        credentials.password.encode("utf8"), correct_password.encode("utf8"))

    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials


app = FastAPI(title="Scheduler Service API", version="1.0.0",
              description="Scheduler Service API",
              openapi_url="/openapi.json",
              docs_url="/docs",
              redoc_url="/redoc",
              dependencies=[Depends(verify_credentials)])

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
