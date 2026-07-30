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
    from app.models.phase import Phase


class CompetitionGroup(Base):
    """Grupo classificativo pertencente a uma fase."""

    __tablename__ = "competition_groups"
    __table_args__ = (
        UniqueConstraint(
            "phase_id",
            "group_name",
            name="uq_competition_groups_phase_id_group_name",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    phase_id: Mapped[int] = mapped_column(
        ForeignKey("phases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    competition_level: Mapped[int] = mapped_column(nullable=False)
    fpf_competition_id: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
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

    phase: Mapped["Phase"] = relationship(
        back_populates="groups",
    )
