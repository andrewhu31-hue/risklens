import os
import uuid
from datetime import date, datetime

from dotenv import load_dotenv
from sqlalchemy import Date, DateTime, Float, ForeignKey, String, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

load_dotenv()


def _new_id() -> str:
    # UUIDs instead of sequential integers so portfolio IDs can't be
    # enumerated (there's no auth/ownership check yet, so a guessable ID
    # would let anyone browse someone else's portfolio by incrementing it).
    return str(uuid.uuid4())

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./risklens.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
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


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
