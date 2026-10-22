"""The FastAPI app: only assembles logging, middleware and routers."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.system import router as system_router
from app.core.config import get_settings
from app.core.errors import SanitizedErrorMiddleware
from app.core.logging import configure_logging
from app.version import app_version

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(title="AAL API", version=app_version())

# Added before CORS so it sits inside it: a sanitized error response still
# carries the CORS headers (each added middleware wraps the previous ones).
app.add_middleware(SanitizedErrorMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system_router)
