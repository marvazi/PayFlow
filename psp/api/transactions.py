from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from psp.api.dependencies import get_transaction_service, verify_api_key
from psp.core.exceptions import IdempotencyConflictError, TransactionNotFoundError, InvalidTransactionStatusError
from psp.schemas.transaction import TransactionResponse, TransactionCreate, TransactionComplete
from psp.services.transaction import TransactionService

router = APIRouter(prefix="/transactions", tags=["transactions"],dependencies=[Depends(verify_api_key)])

@router.post("", response_model=TransactionResponse,status_code=status.HTTP_200_OK)
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

@router.post("/{transaction_id}/complete", response_model=TransactionResponse,status_code=status.HTTP_200_OK)
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

@router.get("/{transaction_id}", response_model=TransactionResponse,status_code=status.HTTP_200_OK)
async def get_transaction(
        transaction_id: UUID,
        service: TransactionService = Depends(get_transaction_service),
):
    try:
        transaction = await service.get(transaction_id=transaction_id)
    except TransactionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return transaction