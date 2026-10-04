"""SQLAlchemy database models for the 3-person shared expense tracker."""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    Date,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utc_now():
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class User(Base):
    """User model for the 3 fixed users."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    expenses = relationship("Expense", back_populates="payer", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} username='{self.username}' name='{self.name}'>"


class Expense(Base):
    """Expense model for shared expenses."""

    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    description = Column(String(255), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    category = Column(String(50), nullable=False, index=True)
    paid_by = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    expense_date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    payer = relationship("User", back_populates="expenses", lazy="joined")

    def __repr__(self) -> str:
        return (
            f"<Expense id={self.id} desc='{self.description}' "
            f"amount={self.amount} paid_by={self.paid_by} date={self.expense_date}>"
        )


class WeeklySummary(Base):
    """Weekly summary model to archive closed week totals and prevent modifications."""

    __tablename__ = "weekly_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    week_start = Column(Date, nullable=False, index=True)
    week_end = Column(Date, nullable=False, index=True)
    total_expenses = Column(Numeric(10, 2), nullable=False)
    person_1_paid = Column(Numeric(10, 2), nullable=False)
    person_2_paid = Column(Numeric(10, 2), nullable=False)
    person_3_paid = Column(Numeric(10, 2), nullable=False)
    person_1_share = Column(Numeric(10, 2), nullable=False)
    person_2_share = Column(Numeric(10, 2), nullable=False)
    person_3_share = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("week_start", "week_end", name="uq_weekly_summary_period"),
    )

    def __repr__(self) -> str:
        return (
            f"<WeeklySummary id={self.id} period={self.week_start} to {self.week_end} "
            f"total={self.total_expenses}>"
        )
