from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


async def app_exception_handler(
    _request: Request,
    exc: Any,  # noqa: ANN401
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.name,
            "message": exc.message,
        },
    )
