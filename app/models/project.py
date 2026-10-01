from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.annotation_file import AnnotationFile
    from app.models.vcf_file import VCFFile


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    vcf_files: Mapped[list["VCFFile"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )

    annotation_files: Mapped[list["AnnotationFile"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
