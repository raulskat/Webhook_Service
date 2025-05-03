# app/main.py

from fastapi import FastAPI, Depends, HTTPException, Request, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app import models, schemas, tasks
from app.database import SessionLocal, init_db
from app.cache import invalidate_subscription_cache
from app.schemas import SubscriptionCreate

# Initialize database tables
init_db()

# Rate limiter configuration
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title="Webhook Service API",
    description="""
    A robust webhook service that handles subscription management, webhook delivery, and retry mechanisms.
    
    ## Features
    - Subscription Management (CRUD operations)
    - Asynchronous Webhook Delivery
    - Signature Verification
    - Automatic Retry with Exponential Backoff
    - Delivery Logging and Analytics
    - Rate Limiting
    - Input Validation
    
    ## Rate Limits
    - Subscriptions: 10 requests per minute
    - Webhooks: 100 requests per minute
    - Delivery Attempts: 30 requests per minute
    """,
    version="1.0.0",
    contact={
        "name": "API Support",
        "email": "rahulshekhawat5992@gmail.com"
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT"
    }
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Serve the web UI at the root path
@app.get("/")
async def read_root():
    return FileResponse("app/static/index.html")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add security middleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key header for authentication
api_key_header = APIKeyHeader(name="X-API-Key")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Rate limit configuration
RATE_LIMITS = {
    "subscriptions": "10/minute",
    "webhooks": "100/minute",
    "delivery_attempts": "30/minute"
}

# Subscription CRUD endpoints
@app.post(
    "/subscriptions",
    response_model=schemas.SubscriptionOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Subscription created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "target_url": "https://example.com/webhooks",
                        "event_types": ["user.created", "order.updated"],
                        "created_at": "2025-05-03T12:00:00Z",
                        "is_active": True
                    }
                }
            }
        },
        400: {
            "description": "Invalid input data",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Secret must contain only alphanumeric characters, underscores, and hyphens"
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Rate limit exceeded: 10 per 1 minute"
                    }
                }
            }
        }
    }
)
@limiter.limit(RATE_LIMITS["subscriptions"])
async def create_subscription(
    request: Request,
    subscription: SubscriptionCreate,
    db: Session = Depends(get_db)
):
    # Create new subscription
    db_subscription = models.Subscription(
        target_url=str(subscription.target_url),
        secret=subscription.secret,
        event_types=subscription.event_types,
        is_active=True
    )
    db.add(db_subscription)
    db.commit()
    db.refresh(db_subscription)
    return db_subscription

@app.get(
    "/subscriptions",
    response_model=List[schemas.SubscriptionOut],
    responses={
        200: {
            "description": "List of subscriptions retrieved successfully",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": 1,
                            "target_url": "https://example.com/webhooks",
                            "event_types": ["user.created"],
                            "created_at": "2025-05-03T12:00:00Z",
                            "is_active": True
                        }
                    ]
                }
            }
        }
    }
)
def list_subscriptions(db: Session = Depends(get_db)):
    """
    List all webhook subscriptions.
    
    Returns an array of subscription objects.
    """
    return db.query(models.Subscription).all()

@app.get(
    "/subscriptions/{id}",
    response_model=schemas.SubscriptionOut,
    responses={
        200: {
            "description": "Subscription retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "target_url": "https://example.com/webhooks",
                        "event_types": ["user.created"],
                        "created_at": "2025-05-03T12:00:00Z",
                        "is_active": True
                    }
                }
            }
        },
        404: {
            "description": "Subscription not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Subscription not found"
                    }
                }
            }
        }
    }
)
def get_subscription(id: int, db: Session = Depends(get_db)):
    """
    Get a specific subscription by ID.
    
    - **id**: The subscription ID
    
    Returns the subscription details if found.
    """
    subscription = db.query(models.Subscription).filter(models.Subscription.id == id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription

@app.put(
    "/subscriptions/{id}",
    response_model=schemas.SubscriptionOut,
    responses={
        200: {
            "description": "Subscription updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "target_url": "https://example.com/webhooks",
                        "event_types": ["user.created", "order.updated"],
                        "created_at": "2025-05-03T12:00:00Z",
                        "is_active": True
                    }
                }
            }
        },
        404: {
            "description": "Subscription not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Subscription not found"
                    }
                }
            }
        }
    }
)
def update_subscription(id: int, subscription: schemas.SubscriptionUpdate, db: Session = Depends(get_db)):
    """
    Update a subscription.
    
    - **id**: The subscription ID
    - **target_url**: (Optional) New target URL
    - **secret**: (Optional) New secret key
    - **event_types**: (Optional) New list of event types
    - **is_active**: (Optional) New active status
    
    Returns the updated subscription.
    """
    db_subscription = db.query(models.Subscription).filter(models.Subscription.id == id).first()
    if not db_subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    update_data = subscription.dict(exclude_unset=True)
    if "target_url" in update_data:
        update_data["target_url"] = str(update_data["target_url"])
    
    for key, value in update_data.items():
        setattr(db_subscription, key, value)
    
    db.commit()
    db.refresh(db_subscription)
    
    # Invalidate cache after update
    invalidate_subscription_cache(id)
    
    return db_subscription

@app.delete("/subscriptions/{id}")
async def delete_subscription(id: int, db: Session = Depends(get_db)):
    """
    Delete a subscription and its related records.
    """
    # First check if subscription exists
    subscription = db.query(models.Subscription).filter(models.Subscription.id == id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    try:
        # Delete related delivery attempts
        db.query(models.DeliveryAttempt).filter(
            models.DeliveryAttempt.subscription_id == id
        ).delete()

        # Delete related webhooks
        db.query(models.Webhook).filter(
            models.Webhook.subscription_id == id
        ).delete()

        # Delete the subscription
        db.delete(subscription)
        db.commit()

        # Invalidate cache
        invalidate_subscription_cache(id)

        return {"message": "Subscription and all related records deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting subscription: {str(e)}"
        )

# Webhook ingestion endpoint
@app.post("/ingest/{subscription_id}", response_model=schemas.WebhookResponse)
async def ingest_webhook(
    subscription_id: int,
    payload: schemas.WebhookPayload,
    db: Session = Depends(get_db)
):
    """
    Ingest a webhook for delivery.
    
    - **subscription_id**: The ID of the subscription to deliver the webhook to
    - **payload**: The webhook payload and event type
    
    Returns a confirmation that the webhook has been queued for delivery.
    """
    # Check if subscription exists and is active
    subscription = db.query(models.Subscription).filter(
        models.Subscription.id == subscription_id,
        models.Subscription.is_active == True
    ).first()
    
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found or inactive")
    
    # Check if event type is allowed for this subscription
    if payload.event_type not in subscription.event_types:
        raise HTTPException(
            status_code=400,
            detail=f"Event type '{payload.event_type}' is not allowed for this subscription"
        )
    
    # Create webhook record
    webhook = models.Webhook(
        subscription_id=subscription_id,
        payload=payload.payload,
        event_type=payload.event_type,
        status="pending"
    )
    db.add(webhook)
    db.commit()
    db.refresh(webhook)
    
    # Queue webhook for delivery
    tasks.deliver_webhook.delay(
        subscription_id=subscription_id,
        webhook_id=webhook.id,
        payload=payload.payload,
        event_type=payload.event_type
    )
    
    return schemas.WebhookResponse(
        status="accepted",
        message="Webhook queued for delivery"
    )

# Delivery history endpoints
@app.get("/subscriptions/{subscription_id}/delivery-attempts", response_model=List[schemas.DeliveryAttemptOut])
async def get_delivery_attempts(
    subscription_id: int,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    """Get delivery attempts for a subscription"""
    subscription = db.query(models.Subscription).filter(models.Subscription.id == subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    attempts = db.query(models.DeliveryAttempt)\
        .filter(models.DeliveryAttempt.subscription_id == subscription_id)\
        .order_by(models.DeliveryAttempt.created_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()
    
    return attempts

@app.get(
    "/delivery-attempts/status/{attempt_id}",
    response_model=schemas.DeliveryAttemptOut,
    responses={
        200: {
            "description": "Delivery attempt status retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "subscription_id": 1,
                        "status_code": 200,
                        "response_body": "{\"status\": \"received\"}",
                        "error_message": None,
                        "attempt_number": 1,
                        "created_at": "2025-05-03T12:00:00Z",
                        "is_success": True
                    }
                }
            }
        },
        404: {
            "description": "Delivery attempt not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Delivery attempt not found"
                    }
                }
            }
        }
    }
)
def get_delivery_status(attempt_id: int, db: Session = Depends(get_db)):
    """
    Get the status of a specific delivery attempt.
    
    - **attempt_id**: The ID of the delivery attempt
    
    Returns the delivery attempt details if found.
    """
    attempt = db.query(models.DeliveryAttempt).filter(
        models.DeliveryAttempt.id == attempt_id
    ).first()
    
    if not attempt:
        raise HTTPException(status_code=404, detail="Delivery attempt not found")
    
    return attempt

@app.get("/delivery-attempts/{attempt_id}", response_model=schemas.DeliveryAttemptOut)
async def get_delivery_attempt_by_id(attempt_id: int, db: Session = Depends(get_db)):
    """
    Get a specific delivery attempt by ID.
    """
    attempt = db.query(models.DeliveryAttempt).filter(models.DeliveryAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Delivery attempt not found")
    return attempt

# Health check endpoint
@app.get(
    "/health",
    responses={
        200: {
            "description": "Service is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy"
                    }
                }
            }
        }
    }
)
def health_check():
    """
    Check the health status of the service.
    
    Returns a simple health status message.
    """
    return {"status": "healthy"}

# Debug endpoint
@app.get("/debug/subscription/{id}")
def debug_subscription(id: int, db: Session = Depends(get_db)):
    subscription = db.query(models.Subscription).filter(models.Subscription.id == id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return {
        "id": subscription.id,
        "target_url": subscription.target_url,
        "event_types": subscription.event_types,
        "is_active": subscription.is_active,
        "created_at": subscription.created_at
    }

# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred"}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8081, reload=True)
