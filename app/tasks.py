import requests
import hmac
import hashlib
import json
from celery import Celery
from celery.schedules import crontab
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv
import logging

from app import models
from app.database import SessionLocal
from app.cache import get_cached_subscription, cache_subscription

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Constants
MAX_DELIVERY_ATTEMPTS = 5
INITIAL_RETRY_DELAY = 10  # seconds
MAX_RETRY_DELAY = 900  # 15 minutes

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_DB = os.getenv("REDIS_DB", "0")

# Celery configuration
celery_app = Celery('webhook_tasks')
celery_app.conf.broker_url = f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
celery_app.conf.result_backend = f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'

# Enable task events and set log level
celery_app.conf.worker_send_task_events = True
celery_app.conf.task_send_sent_event = True
celery_app.conf.worker_log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
celery_app.conf.worker_task_log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
celery_app.conf.worker_redirect_stdouts = True
celery_app.conf.worker_redirect_stdouts_level = 'DEBUG'

celery_app.conf.task_routes = {
    'app.tasks.deliver_webhook': 'webhook-queue',
    'app.tasks.cleanup_old_logs': 'cleanup-queue'
}

# Retry configuration
celery_app.conf.task_default_retry_delay = INITIAL_RETRY_DELAY
celery_app.conf.task_max_retries = MAX_DELIVERY_ATTEMPTS
celery_app.conf.task_retry_backoff = True
celery_app.conf.task_retry_backoff_max = MAX_RETRY_DELAY

def generate_signature(secret: str, payload: dict) -> str:
    """Generate HMAC signature for webhook payload"""
    return hmac.new(
        secret.encode(),
        json.dumps(payload).encode(),
        hashlib.sha256
    ).hexdigest()

def calculate_retry_delay(attempt_number: int) -> int:
    """Calculate delay for next retry attempt using exponential backoff"""
    delay = INITIAL_RETRY_DELAY * (2 ** (attempt_number - 1))
    return min(delay, MAX_RETRY_DELAY)

@celery_app.task
def deliver_webhook(subscription_id: int, webhook_id: int, payload: dict, event_type: str):
    """Deliver webhook to subscription target URL"""
    logger.info(f"\n=== Starting webhook delivery for subscription {subscription_id} ===")
    logger.info(f"Payload: {payload}")
    logger.info(f"Event type: {event_type}")
    
    db = SessionLocal()
    try:
        # Get subscription from cache or database
        subscription = get_cached_subscription(subscription_id)
        if not subscription:
            logger.info(f"Subscription {subscription_id} not in cache, querying database")
            subscription = db.query(models.Subscription).filter(
                models.Subscription.id == subscription_id,
                models.Subscription.is_active == True
            ).first()
            if subscription:
                cache_subscription(subscription)
        
        if not subscription:
            logger.error(f"Subscription {subscription_id} not found or inactive")
            return
        
        # Create delivery attempt record
        logger.info(f"Creating delivery attempt record for subscription {subscription_id}")
        attempt = models.DeliveryAttempt(
            subscription_id=subscription_id,
            webhook_id=webhook_id,
            attempt_number=1,
            status_code=None,
            response_body=None,
            error_message=None,
            is_success=False
        )
        db.add(attempt)
        db.commit()
        
        # Prepare request
        headers = {
            "Content-Type": "application/json",
            "X-Event-Type": event_type,
            "X-Hook-Signature": generate_signature(subscription.secret, payload)
        }
        
        # Send webhook
        try:
            response = requests.post(
                subscription.target_url,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            # Update delivery attempt
            attempt.status_code = response.status_code
            attempt.response_body = response.text
            attempt.is_success = response.status_code in [200, 201, 202]
            
            if not attempt.is_success:
                attempt.error_message = f"Received status code {response.status_code}"
            
            db.commit()
            logger.info(f"Webhook delivered successfully with status code {response.status_code}")
            
        except requests.exceptions.RequestException as e:
            # Update delivery attempt with error
            attempt.error_message = str(e)
            db.commit()
            logger.error(f"Error delivering webhook: {str(e)}")
            
            # Retry if not exceeded max attempts
            if attempt.attempt_number < MAX_DELIVERY_ATTEMPTS:
                retry_delay = calculate_retry_delay(attempt.attempt_number)
                logger.info(f"Scheduling retry in {retry_delay} seconds")
                deliver_webhook.apply_async(
                    args=[subscription_id, webhook_id, payload, event_type],
                    countdown=retry_delay
                )
            else:
                logger.error("Max delivery attempts exceeded")
        
    except Exception as e:
        logger.error(f"Error in webhook delivery: {str(e)}")
        if 'attempt' in locals():
            attempt.error_message = str(e)
            db.commit()
    finally:
        db.close()
        logger.info("=== Webhook delivery task completed ===")

@celery_app.task
def cleanup_old_logs():
    """Delete delivery attempts older than 72 hours"""
    logger.info("Starting cleanup of old delivery attempts")
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(hours=72)
        logger.info(f"Deleting delivery attempts older than {cutoff}")
        
        # Get count before deletion
        old_attempts = db.query(models.DeliveryAttempt).filter(
            models.DeliveryAttempt.created_at < cutoff
        ).count()
        
        if old_attempts > 0:
            # Delete old attempts
            db.query(models.DeliveryAttempt).filter(
                models.DeliveryAttempt.created_at < cutoff
            ).delete()
            db.commit()
            logger.info(f"Successfully deleted {old_attempts} old delivery attempts")
        else:
            logger.info("No old delivery attempts to delete")
            
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()
        logger.info("Cleanup task completed")

# Schedule cleanup task to run every hour
celery_app.conf.beat_schedule = {
    'cleanup-old-logs': {
        'task': 'app.tasks.cleanup_old_logs',
        'schedule': crontab(minute=0),
        'options': {
            'queue': 'cleanup-queue',
            'expires': 3600  # Task expires after 1 hour if not picked up
        }
    }
}
