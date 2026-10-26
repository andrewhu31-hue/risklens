import os
import uuid
from datetime import date, datetime

from dotenv import load_dotenv
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import NullPool

load_dotenv()


def _new_id() -> str:
    # UUIDs instead of sequential integers so portfolio IDs can't be enumerated
    # (defence in depth on top of the ownership check).
    return str(uuid.uuid4())



def _database_url() -> str:
    """DATABASE_URL (or the POSTGRES_URL a Vercel/Neon integration injects),
    normalized for SQLAlchemy + psycopg 3. Without one, SQLite: ./risklens.db
    locally, /tmp on Vercel (the only writable path there — not persistent)."""
    url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or ""
    if not url:
        return "sqlite:////tmp/risklens.db" if os.getenv("VERCEL") else "sqlite:///./risklens.db"
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


DATABASE_URL = _database_url()
IS_SQLITE = DATABASE_URL.startswith("sqlite")

connect_args = {"check_same_thread": False, "timeout": 30} if IS_SQLITE else {}
engine_kwargs: dict = {"connect_args": connect_args, "pool_pre_ping": not IS_SQLITE}
if os.getenv("VERCEL") and not IS_SQLITE:
    # Serverless instances come and go; don't hold idle connections open.
    engine_kwargs["poolclass"] = NullPool
engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    benchmark: Mapped[str] = mapped_column(String, default="SPY")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    holdings: Mapped[list["Holding"]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan"
    )


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(ForeignKey("portfolios.id"))
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    shares: Mapped[float] = mapped_column(Float, nullable=False)
    cost_basis: Mapped[float | None] = mapped_column(Float, nullable=True)
    sector: Mapped[str | None] = mapped_column(String, nullable=True)

    portfolio: Mapped["Portfolio"] = relationship(back_populates="holdings")


class PriceHistory(Base):
    __tablename__ = "price_history"
    __table_args__ = (UniqueConstraint("ticker", "date", name="uq_ticker_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String, nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    adj_close: Mapped[float] = mapped_column(Float, nullable=False)


class PriceFetch(Base):
    """One row per ticker: when the provider was last asked, and whether the full
    history has been loaded. Lets the cache skip repeat calls (including for
    tickers the provider has no data for) and know when a backfill is needed."""

    __tablename__ = "price_fetch"

    ticker: Mapped[str] = mapped_column(String, primary_key=True)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    checked_for: Mapped[date | None] = mapped_column(Date, nullable=True)
    full_history: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str | None] = mapped_column(String, nullable=True)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
