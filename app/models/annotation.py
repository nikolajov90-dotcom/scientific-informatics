from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.variant import Variant


class Annotation(Base):
    __tablename__ = "annotations"

    id: Mapped[int] = mapped_column(primary_key=True)

    variant_id: Mapped[int] = mapped_column(
        ForeignKey("variants.id"),
        nullable=False,
    )

    gene: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    clinical_significance: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    variant: Mapped["Variant"] = relationship(
        back_populates="annotation",
    )
