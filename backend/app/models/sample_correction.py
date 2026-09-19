from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SampleCorrection(Base):
    """粘度取样的更正记录。

    只能追加，不能覆盖原取样行的 viscosity_pa_s / sampled_at。
    同一取样可有多条；有效粘度取 corrected_at 最新、再按 id 最新的一条。
    """

    __tablename__ = "sample_corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sample_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("viscosity_samples.id", ondelete="CASCADE"),
        nullable=False,
    )
    viscosity_pa_s: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    sample: Mapped["ViscositySample"] = relationship(
        "ViscositySample", back_populates="corrections"
    )
