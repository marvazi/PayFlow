from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from starlette import status
from starlette.responses import Response

from app.api.dependencies import get_payment_service, verify_webhook
from app.core.exeptions import (
    InvalidInvoiceStatusError,
    InvalidPaymentStatusError,
    InvoiceNotFoundError,
    PaymentNotFoundError,
    PaymentWebhookConflictError,
)
from app.schemas.payment import PaymentWebhookPayload
from app.services.payment import PaymentService

router = APIRouter(
    prefix="/webhooks",
    tags=["webhook"],
)


@router.post(
    "/psp",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(verify_webhook)],
)
async def receive_webhook(
    payload: PaymentWebhookPayload,
    service: Annotated[PaymentService, Depends(get_payment_service)],
):
    try:
        await service.process_result(payload)
    except (PaymentNotFoundError, InvoiceNotFoundError) as ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ex))
    except (
        PaymentWebhookConflictError,
        InvalidPaymentStatusError,
        InvalidInvoiceStatusError,
    ) as ex:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(ex))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
