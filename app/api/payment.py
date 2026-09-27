from uuid import UUID
from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from starlette import status
from app.schemas.invoice import InvoiceResponse, InvoiceCreate, InvoiceUpdate
from app.schemas.payment import PaymentResponse, PaymentCreate
from app.services.invoice import InvoiceService
from app.api.dependencies import get_current_user, get_invoice_service, get_payment_service
from app.core.exeptions import OrganizationNotFoundError, PermissionDeniedError, InvoiceNotFoundError, \
    CustomerNotFoundError, InvoiceNotEditableError, \
    InvalidInvoiceStatusError, PaymentAlreadyPendingError, PaymentNotFoundError
from app.models import User, Invoice, Payment
from app.services.payment import PaymentService

router = APIRouter(
    prefix="/organization/{organization_id}/payments",
    tags=["payment"],
)

@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
        data:PaymentCreate,
        organization_id:UUID,
        service:PaymentService = Depends(get_payment_service),
        user: User = Depends(get_current_user),
) -> Payment:
    try:
        created_payment = await service.create(
            actor_id=user.id,
            organization_id=organization_id,
            data=data,

        )
        return created_payment
    except (OrganizationNotFoundError, InvoiceNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (InvalidInvoiceStatusError, PaymentAlreadyPendingError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.get("/{payment_id}", response_model=PaymentResponse, status_code=status.HTTP_200_OK)
async def get_payment(
        payment_id:UUID,
        organization_id:UUID,
        service:PaymentService = Depends(get_payment_service),
        user: User = Depends(get_current_user),
)->Payment:
    try:
        payment = await service.get_payment(
            actor_id=user.id,
            organization_id=organization_id,
            payment_id=payment_id,
        )
        return payment
    except OrganizationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@router.get("", response_model=list[PaymentResponse],status_code=status.HTTP_200_OK)
async def get_payments(
        invoice_id:UUID,
        organization_id: UUID,
        service: PaymentService = Depends(get_payment_service),
        user: User = Depends(get_current_user),
)->list[Payment]:
    try:
        list_payments = await service.list_payments(
            actor_id=user.id,
            organization_id=organization_id,
            invoice_id=invoice_id,
        )
        return list_payments
    except (OrganizationNotFoundError, InvoiceNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc