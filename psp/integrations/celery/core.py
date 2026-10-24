from celery import Celery

from psp.core.config import settings

celery_app = Celery(
    "psp",
    broker=settings.celery_broker_url,
    include=["psp.integrations.celery.tasks"],
)