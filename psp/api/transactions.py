import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from psp.api.dependencies import get_transaction_service, verify_api_key
from psp.core.exceptions import (
    IdempotencyConflictError,
    InvalidTransactionStatusError,
    PayFlowInvalidResponseError,
    PayFlowUnavailableError,
    PayFlowWebhookConflictError,
    TransactionNotFoundError,
)
from psp.schemas.transaction import (
    TransactionComplete,
    TransactionCreate,
    TransactionResponse,
)
from psp.services.transaction import TransactionService

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/transactions",
    tags=["transactions"],
    dependencies=[Depends(verify_api_key)],
)


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_200_OK)
async def create_transaction(
    data: TransactionCreate,
    service: TransactionService = Depends(get_transaction_service),
):
    try:
        created_transaction = await service.create(
            data=data,
        )
        return created_transaction
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/{transaction_id}/complete",
    response_model=TransactionResponse,
    status_code=status.HTTP_200_OK,
)
async def complete_transaction(
    data: TransactionComplete,
    transaction_id: UUID,
    service: TransactionService = Depends(get_transaction_service),
):
    try:
        completed_transaction = await service.complete(
            status=data.status,
            transaction_id=transaction_id,
        )
        return completed_transaction
    except TransactionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidTransactionStatusError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PayFlowUnavailableError as exc:
        logger.exception(
            "Не удалось подтвердить доставку вебхука: transaction_id=%s",
            transaction_id,
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Результат транзакции сохранён, но доставку уведомления "
                "подтвердить не удалось. Повторите запрос с тем же статусом."
            ),
        ) from exc

    except PayFlowWebhookConflictError as exc:
        logger.exception(
            "PayFlow отклонил вебхук из-за конфликта: transaction_id=%s",
            transaction_id,
        )
        raise HTTPException(
            status_code=409,
            detail=(
                "Результат PSP сохранён, но PayFlow отклонил уведомление "
                "из-за конфликта данных или статуса."
            ),
        ) from exc

    except PayFlowInvalidResponseError as exc:
        logger.exception(
            "PayFlow отклонил вебхук: transaction_id=%s",
            transaction_id,
        )
        raise HTTPException(
            status_code=502,
            detail=(
                "Результат PSP сохранён, но PayFlow отклонил уведомление. "
                "Проверьте настройки интеграции и логи."
            ),
        ) from exc


@router.get(
    "/{transaction_id}",
    response_model=TransactionResponse,
    status_code=status.HTTP_200_OK,
)
async def get_transaction(
    transaction_id: UUID,
    service: TransactionService = Depends(get_transaction_service),
):
    try:
        transaction = await service.get(transaction_id=transaction_id)
    except TransactionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return transaction
