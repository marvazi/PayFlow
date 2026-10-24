import asyncio

import httpx

from psp.core.config import settings
from psp.integrations.payflow.client.client import PayFlowClient
from psp.integrations.payflow.client.schemas import PayFlowWebhookPayload
from psp.integrations.celery.core import celery_app

async def delivery_webhook(payload:dict):
    pydantic_model = PayFlowWebhookPayload.model_validate(payload)
    async with httpx.AsyncClient(
        base_url=settings.payflow_base_url,
        timeout=settings.payflow_timeout_seconds,
        headers={
            "X-Webhook-Secret": settings.payflow_webhook_secret
        },
    ) as client:
        payflow_client= PayFlowClient(client)
        await payflow_client.transaction_webhook(payload=pydantic_model)


@celery_app.task
def delivery_webhook_task(payload: dict) -> None:
    asyncio.run(delivery_webhook(payload))