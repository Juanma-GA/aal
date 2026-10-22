from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# The states of a module (E02): only a "disponible" module has a route.
MODULE_STATUSES = ("planificado", "en_desarrollo", "disponible")


class ModuleGroup(Base):
    """A group of the PALI menu (Inicio, Base común, PAAL...)."""

    __tablename__ = "module_group"

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class ModuleCatalog(Base):
    """One module of the PALI (D7): what it is for (objective, inputs,
    outputs, deliverable, dependencies) and how far it is. Texts come from
    app/seeds/module_catalog_seed.yaml; status and route are changed by an
    admin (Ajustes -> Módulos) and never overwritten by a reload."""

    __tablename__ = "module_catalog"
    __table_args__ = (
        CheckConstraint("status IN ('planificado', 'en_desarrollo', 'disponible')", name="ck_module_catalog_status"),
        CheckConstraint("(status = 'disponible') = (route IS NOT NULL)", name="ck_module_catalog_route"),
    )

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    group_code: Mapped[str] = mapped_column(String(50), ForeignKey("module_group.code"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="planificado")
    encargo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    objective: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    inputs: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    outputs: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    deliverable: Mapped[str | None] = mapped_column(Text, nullable=True)
    dependencies: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    route: Mapped[str | None] = mapped_column(String(200), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ModuleRequirement(Base):
    """A client requirement (RF-xx) a module covers, with its text."""

    __tablename__ = "module_requirement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    module_code: Mapped[str] = mapped_column(
        String(50), ForeignKey("module_catalog.code", ondelete="CASCADE"), nullable=False, index=True
    )
    rf_id: Mapped[str] = mapped_column(String(10), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
