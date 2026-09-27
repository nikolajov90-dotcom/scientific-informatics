from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.variant import Variant


class VCFFile(Base):
    __tablename__ = "vcf_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    project: Mapped["Project"] = relationship(
        back_populates="vcf_files",
    )

    variants: Mapped[list["Variant"]] = relationship(
        back_populates="vcf_file",
        cascade="all, delete-orphan",
    )
