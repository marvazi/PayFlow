import httpx

from psp.core.exceptions import (
    PayFlowInvalidResponseError,
    PayFlowUnavailableError,
    PayFlowWebhookConflictError,
)
from psp.integrations.payflow.client.schemas import PayFlowWebhookPayload


class PayFlowClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def transaction_webhook(
        self,
        payload: PayFlowWebhookPayload,
    ) -> None:
        try:
            response = await self.client.post(
                "/webhooks/psp",
                json=payload.model_dump(mode="json"),
            )
            print("Webhook response:", response.status_code, response.text)
            print("Webhook URL:", response.request.url)
            response.raise_for_status()

        except httpx.TimeoutException as exc:
            raise PayFlowUnavailableError("PayFlow не ответил вовремя") from exc

        except httpx.RequestError as exc:
            raise PayFlowUnavailableError("Не удалось связаться с PayFlow") from exc

        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code

            if status_code == 409:
                raise PayFlowWebhookConflictError(
                    "PayFlow отклонил вебхук из-за конфликта данных или статуса"
                ) from exc

            if 500 <= status_code <= 599:
                raise PayFlowUnavailableError("Ошибка на стороне PayFlow") from exc

            raise PayFlowInvalidResponseError(
                f"PayFlow отклонил вебхук: HTTP {status_code}"
            ) from exc
