"""Tracks whether an Attention Score flag actually preceded a further move —
the self-audit that keeps the score honest rather than a black box that
just asserts significance and moves on."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class FlaggedEvent(Base):
    __tablename__ = "flagged_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    watchlist_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    attention_label: Mapped[str] = mapped_column(String(16), nullable=False)
    attention_score: Mapped[float] = mapped_column(Float, nullable=False)
    price_at_flag: Mapped[float] = mapped_column(Float, nullable=False)
    flagged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    evaluated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    outcome_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)