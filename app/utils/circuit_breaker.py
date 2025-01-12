import logging
from datetime import timedelta, datetime
from aiobreaker import CircuitBreakerError, CircuitBreakerListener, CircuitBreaker
import aiohttp

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


breaker = CircuitBreaker(
    fail_max=5,
    timeout_duration=timedelta(seconds=60),
    listeners=[CustomCircuitBreakerListener()]
)


@breaker
async def make_request(url: str, payload: dict) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, timeout=10) as response:
            response.raise_for_status()
            return await response.json()


async def execute_callback_async(url: str, payload: dict):
    try:
        logger.info(f"Executing callback to {url} with payload {payload}")
        result = await make_request(url, payload)
        logger.info(f"Callback executed successfully: {result}")

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
