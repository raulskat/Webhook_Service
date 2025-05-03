import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_BROKER_URL = os.getenv("REDIS_BROKER_URL")

celery = Celery("tasks", broker=REDIS_BROKER_URL)


@celery.task
def deliver_webhook(subscription_id: int, payload: dict):
    # placeholder logic for webhook delivery
    print(f"Delivering to {subscription_id} with payload: {payload}")
