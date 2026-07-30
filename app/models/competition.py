from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Competition(Base):
    """Competição desportiva disponível no FootballIQ."""

    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    internal_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    association_id: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )
    season_id: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )
    season_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
