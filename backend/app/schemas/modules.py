from pydantic import BaseModel, Field

from app.schemas.common import StrictModel


class ModuleBrief(BaseModel):
    code: str
    name: str
    sort_order: int
    phase: str
    status: str
    route: str | None
    version: int


class ModuleGroupOut(BaseModel):
    code: str
    name: str
    sort_order: int
    modules: list[ModuleBrief]


class ModuleLink(BaseModel):
    code: str
    name: str
    status: str
    group_code: str


class RequirementOut(BaseModel):
    rf_id: str
    text: str


class ModuleDetail(ModuleBrief):
    group_code: str
    group_name: str
    encargo: str | None
    objective: str
    inputs: list[str]
    outputs: list[str]
    deliverable: str | None
    requirements: list[RequirementOut]
    depends_on: list[ModuleLink]
    used_by: list[ModuleLink]


class ModuleUpdate(StrictModel):
    version: int
    status: str | None = Field(default=None, max_length=20)
    route: str | None = Field(default=None, max_length=200)
