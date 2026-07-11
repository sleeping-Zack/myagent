from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class KnowledgeNotFoundError(Exception):
    pass


class InsufficientEvidenceError(Exception):
    pass


class RateLimitError(Exception):
    pass


class InputValidationError(Exception):
    pass


async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": "内部服务错误"})
