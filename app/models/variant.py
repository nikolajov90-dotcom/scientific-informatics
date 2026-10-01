from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.vcf_file import VCFFile


class Variant(Base):
    __tablename__ = "variants"

    id: Mapped[int] = mapped_column(primary_key=True)

    vcf_file_id: Mapped[int] = mapped_column(
        ForeignKey("vcf_files.id"),
        nullable=False,
    )

    chrom: Mapped[str] = mapped_column(String(50), nullable=False)
    pos: Mapped[int] = mapped_column(Integer, nullable=False)
    ref: Mapped[str] = mapped_column(String(255), nullable=False)
    alt: Mapped[str] = mapped_column(String(255), nullable=False)
    qual: Mapped[float | None] = mapped_column(Float, nullable=True)
    filter: Mapped[str | None] = mapped_column(String(255), nullable=True)
    af: Mapped[float | None] = mapped_column(Float, nullable=True)

    vcf_file: Mapped["VCFFile"] = relationship(
        back_populates="variants",
    )
