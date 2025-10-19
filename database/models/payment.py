"""Payment and subscription models."""

from sqlalchemy import Column, String, Integer, DateTime, Boolean, Enum, Text
from sqlalchemy.sql import func
from .base import Base
import enum


class SubscriptionStatus(str, enum.Enum):
    """Subscription status enum."""
    ACTIVE = "active"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    PAST_DUE = "past_due"
    TRIALING = "trialing"
    UNPAID = "unpaid"


class Customer(Base):
    """Stripe customer model."""
    
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True, nullable=False)  # Your app's user ID
    stripe_customer_id = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, index=True, nullable=False)
    name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Subscription(Base):
    """Stripe subscription model."""
    
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    stripe_subscription_id = Column(String, unique=True, index=True, nullable=False)
    stripe_customer_id = Column(String, index=True, nullable=False)
    status = Column(Enum(SubscriptionStatus), nullable=False)
    price_id = Column(String, nullable=False)
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = Column(Boolean, default=False)
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PaymentHistory(Base):
    """Payment history model."""
    
    __tablename__ = "payment_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    stripe_payment_intent_id = Column(String, unique=True, index=True, nullable=False)
    stripe_customer_id = Column(String, index=True, nullable=False)
    amount = Column(Integer, nullable=False)  # Amount in cents
    currency = Column(String, nullable=False, default="usd")
    status = Column(String, nullable=False)  # succeeded, pending, failed, etc.
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

