"""The FastAPI app: only assembles logging, middleware and routers."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.admin import router as admin_router
from app.api.routes.auth import router as auth_router
from app.api.routes.materials import router as materials_router
from app.api.routes.me import router as me_router
from app.api.routes.system import router as system_router
from app.api.routes.users import router as users_router
from app.core.config import get_settings
from app.core.errors import SanitizedErrorMiddleware, validation_error_handler
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

app.add_exception_handler(RequestValidationError, validation_error_handler)

app.include_router(system_router)
app.include_router(auth_router)
app.include_router(me_router)
app.include_router(users_router)
app.include_router(materials_router)
app.include_router(admin_router)
