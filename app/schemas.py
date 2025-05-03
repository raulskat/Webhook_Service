# app/schemas.py

from pydantic import BaseModel, HttpUrl, Field, validator
from typing import List, Optional
from datetime import datetime
import re

class SubscriptionCreate(BaseModel):
    target_url: HttpUrl = Field(..., description="The URL where webhooks will be delivered")
    secret: str = Field(..., min_length=8, max_length=64, description="Secret key for webhook signature verification")
    event_types: List[str] = Field(..., min_items=1, max_items=10, description="List of event types to subscribe to")

    @validator('secret')
    def validate_secret(cls, v):
        if not re.match(r'^[a-zA-Z0-9_\-]+$', v):
            raise ValueError('Secret must contain only alphanumeric characters, underscores, and hyphens')
        return v

    @validator('event_types')
    def validate_event_types(cls, v):
        if not all(re.match(r'^[a-zA-Z0-9_\-\.]+$', event) for event in v):
            raise ValueError('Event types must contain only alphanumeric characters, underscores, hyphens, and dots')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "target_url": "https://example.com/webhooks",
                "secret": "my_secure_secret_123",
                "event_types": ["user.created", "order.updated"]
            }
        }

class SubscriptionUpdate(BaseModel):
    target_url: Optional[HttpUrl] = None
    secret: Optional[str] = None
    event_types: Optional[List[str]] = None
    is_active: Optional[bool] = None

    @validator('secret')
    def validate_secret(cls, v):
        if v is not None and not re.match(r'^[a-zA-Z0-9_\-]+$', v):
            raise ValueError('Secret must contain only alphanumeric characters, underscores, and hyphens')
        return v

    @validator('event_types')
    def validate_event_types(cls, v):
        if v is not None and not all(re.match(r'^[a-zA-Z0-9_\-\.]+$', event) for event in v):
            raise ValueError('Event types must contain only alphanumeric characters, underscores, hyphens, and dots')
        return v

class SubscriptionOut(BaseModel):
    id: int
    target_url: HttpUrl
    event_types: List[str]
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        # Convert JSON array back to Python list
        obj.event_types = obj.event_types if isinstance(obj.event_types, list) else []
        return super().from_orm(obj)

class DeliveryAttemptOut(BaseModel):
    id: int
    subscription_id: int
    webhook_id: int
    attempt_number: int
    status_code: Optional[int]
    response_body: Optional[str]
    error_message: Optional[str]
    is_success: bool
    created_at: datetime

    class Config:
        from_attributes = True

class WebhookPayload(BaseModel):
    payload: dict = Field(..., description="The webhook payload data")
    event_type: str = Field(..., min_length=1, max_length=64, description="Type of the webhook event")

    @validator('event_type')
    def validate_event_type(cls, v):
        if not re.match(r'^[a-zA-Z0-9_\-\.]+$', v):
            raise ValueError('Event type must contain only alphanumeric characters, underscores, hyphens, and dots')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "payload": {
                    "user_id": 123,
                    "name": "John Doe",
                    "email": "john@example.com"
                },
                "event_type": "user.created"
            }
        }

class WebhookResponse(BaseModel):
    status: str
    message: str

    class Config:
        json_schema_extra = {
            "example": {
                "status": "accepted",
                "message": "Webhook queued for delivery"
            }
        }
