from pydantic import BaseModel


class MigrationStatus(BaseModel):
    current: str | None
    head: str | None
    up_to_date: bool


class DatabaseStatus(BaseModel):
    status: str
    migrations: MigrationStatus


class HealthResponse(BaseModel):
    status: str
    database: DatabaseStatus


class VersionResponse(BaseModel):
    app: str
    aacf: str | None
