from sqlalchemy import create_engine, Index, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
import os
from dotenv import load_dotenv
import logging
import time
from sqlalchemy.exc import OperationalError, ProgrammingError

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import os

POSTGRES_USER = os.environ["POSTGRES_USER"]
POSTGRES_PASSWORD = os.environ["POSTGRES_PASSWORD"]
POSTGRES_HOST = os.environ["POSTGRES_HOST"]
POSTGRES_PORT = os.environ["POSTGRES_PORT"]
POSTGRES_DB = os.environ["POSTGRES_DB"]

POOL_SIZE = int(os.environ["DB_POOL_SIZE"])
MAX_OVERFLOW = int(os.environ["DB_MAX_OVERFLOW"])
POOL_TIMEOUT = int(os.environ["DB_POOL_TIMEOUT"])
POOL_RECYCLE = int(os.environ["DB_POOL_RECYCLE"])

SQLALCHEMY_DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

def create_engine_with_retry(max_retries=5, retry_delay=5):
    """Create database engine with retry mechanism"""
    for attempt in range(max_retries):
        try:
            engine = create_engine(
                SQLALCHEMY_DATABASE_URL,
                poolclass=QueuePool,
                pool_size=POOL_SIZE,
                max_overflow=MAX_OVERFLOW,
                pool_timeout=POOL_TIMEOUT,
                pool_recycle=POOL_RECYCLE,
                pool_pre_ping=True
            )
            # Test the connection using text() for proper SQL execution
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return engine
        except OperationalError as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed to connect to database after {max_retries} attempts: {str(e)}")
                raise
            logger.warning(f"Database connection attempt {attempt + 1} failed: {str(e)}")
            time.sleep(retry_delay)
    return None

# Create engine with connection pooling
engine = create_engine_with_retry()

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Database event listeners
@event.listens_for(engine, "connect")
def connect(dbapi_connection, connection_record):
    logger.info("New database connection established")

@event.listens_for(engine, "checkout")
def checkout(dbapi_connection, connection_record, connection_proxy):
    logger.debug("Connection checked out from pool")

@event.listens_for(engine, "checkin")
def checkin(dbapi_connection, connection_record):
    logger.debug("Connection returned to pool")

def init_db():
    """Initialize database with tables and indexes"""
    try:
        from .base import Base
        from . import models
        
        # Create all tables if they don't exist
        Base.metadata.create_all(bind=engine)
        
        # Create indexes if they don't exist
        indexes = [
            Index('ix_subscriptions_is_active', models.Subscription.is_active),
            Index('ix_subscriptions_event_types', models.Subscription.event_types, postgresql_using='gin', postgresql_ops={'event_types': 'jsonb_path_ops'}),
            Index('ix_delivery_attempts_subscription_id', models.DeliveryAttempt.subscription_id),
            Index('ix_delivery_attempts_webhook_id', models.DeliveryAttempt.webhook_id),
            Index('ix_delivery_attempts_created_at', models.DeliveryAttempt.created_at),
            Index('ix_delivery_attempts_is_success', models.DeliveryAttempt.is_success),
            Index('ix_webhooks_subscription_id', models.Webhook.subscription_id),
            Index('ix_webhooks_event_type', models.Webhook.event_type),
            Index('ix_webhooks_created_at', models.Webhook.created_at)
        ]
        
        # Create indexes if they don't exist
        for idx in indexes:
            try:
                idx.create(bind=engine)
            except ProgrammingError as e:
                if "already exists" not in str(e):
                    logger.warning(f"Failed to create index {idx.name}: {str(e)}")
            except Exception as e:
                logger.warning(f"Failed to create index {idx.name}: {str(e)}")
        
        logger.info("Database initialized with tables and indexes")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise

# Optional: reusable DB dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
