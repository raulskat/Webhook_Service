# app/models.py (SQLAlchemy model)
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    target_url = Column(String, nullable=False)
    secret = Column(String, nullable=False)
    event_types = Column(JSONB, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    webhooks = relationship("Webhook", back_populates="subscription")
    delivery_attempts = relationship("DeliveryAttempt", back_populates="subscription")

class Webhook(Base):
    __tablename__ = "webhooks"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    payload = Column(JSONB, nullable=False)
    event_type = Column(String, nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    subscription = relationship("Subscription", back_populates="webhooks")
    delivery_attempts = relationship("DeliveryAttempt", back_populates="webhook")

class DeliveryAttempt(Base):
    __tablename__ = "delivery_attempts"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    webhook_id = Column(Integer, ForeignKey("webhooks.id"), nullable=False)
    attempt_number = Column(Integer, nullable=False)
    status_code = Column(Integer)
    response_body = Column(Text)
    error_message = Column(Text)
    is_success = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    subscription = relationship("Subscription", back_populates="delivery_attempts")
    webhook = relationship("Webhook", back_populates="delivery_attempts")
