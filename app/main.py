from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi_pagination import add_pagination
from starlette.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.exceptions.base import AppError
from app.exceptions.handlers import app_exception_handler

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Exception handlers
app.add_exception_handler(AppError, app_exception_handler)

# Include API Router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Pagination setup
add_pagination(app)


@app.get("/", tags=["root"], include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=settings.PORT,
        reload=settings.DEBUG,
    )
