from uuid import UUID

import httpx

from app.core.exeptions import PSPInvalidResponseError, PSPUnavailableError, PSPIdempotencyConflictError
from app.integrations.psp.schemas import PSPTransactionResponse


class PSPClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def create_transaction(
            self, external_payment_id: UUID,
            amount_minor: int,
            currency: str
    ) -> PSPTransactionResponse:
        try:
            response = await self.client.post(
                "/transactions",
                json={
                    "external_payment_id": str(external_payment_id),
                    "amount_minor": amount_minor,
                    "currency": currency
                })
            response.raise_for_status()
            return PSPTransactionResponse.model_validate(response.json())
        except httpx.TimeoutException as exc:
            raise PSPUnavailableError("PSP не ответил вовремя") from exc
        except httpx.RequestError as exc:
            raise PSPUnavailableError("Не удалось связаться с PSP") from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code

            if status_code == 409:
                raise PSPIdempotencyConflictError(
                    "Параметры платежа не совпадают с ранее отправленными"
                ) from exc

            if 500 <= status_code <= 599:
                raise PSPUnavailableError("Ошибка на стороне PSP") from exc

            raise PSPInvalidResponseError("PSP отклонил запрос") from exc
        except ValueError as exc:
            raise PSPInvalidResponseError("Некорректный ответ PSP") from exc
