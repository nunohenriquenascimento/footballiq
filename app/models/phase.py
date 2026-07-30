from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.competition import Competition
    from app.models.competition_group import CompetitionGroup


class Phase(Base):
    """Fase competitiva pertencente a uma competição."""

    __tablename__ = "phases"
    __table_args__ = (
        UniqueConstraint(
            "competition_id",
            "phase_order",
            name="uq_phases_competition_id_phase_order",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phase_order: Mapped[int] = mapped_column(nullable=False)
    phase_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
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

    competition: Mapped["Competition"] = relationship(
        back_populates="phases",
    )
    groups: Mapped[list["CompetitionGroup"]] = relationship(
        back_populates="phase",
        cascade="all, delete-orphan",
    )
