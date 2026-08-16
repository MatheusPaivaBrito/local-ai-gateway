from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UsageEventRecord(Base):
    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    api_key_id: Mapped[int] = mapped_column(ForeignKey("api_keys.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    endpoint: Mapped[str] = mapped_column(String(64), nullable=False)
    public_model: Mapped[str] = mapped_column(String(120), nullable=False)
    upstream_model: Mapped[str] = mapped_column(String(120), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    gpu_name: Mapped[str | None] = mapped_column(String(160))
    gpu_index: Mapped[int | None] = mapped_column(Integer)
    utilization_avg_pct: Mapped[float | None] = mapped_column(Float)
    utilization_peak_pct: Mapped[float | None] = mapped_column(Float)
    memory_peak_mb: Mapped[float | None] = mapped_column(Float)
    temperature_avg_c: Mapped[float | None] = mapped_column(Float)
    temperature_peak_c: Mapped[float | None] = mapped_column(Float)
    power_avg_w: Mapped[float | None] = mapped_column(Float)
    power_peak_w: Mapped[float | None] = mapped_column(Float)
    energy_joules: Mapped[float | None] = mapped_column(Float)
    energy_wh: Mapped[float | None] = mapped_column(Float)
    energy_source: Mapped[str | None] = mapped_column(String(48))
    joules_per_output_token: Mapped[float | None] = mapped_column(Float)
    output_tokens_per_wh: Mapped[float | None] = mapped_column(Float)
    output_tokens_per_second: Mapped[float | None] = mapped_column(Float)
    estimated_energy_cost: Mapped[float | None] = mapped_column(Float)
