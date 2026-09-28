from uuid import UUID
from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from starlette import status
from app.schemas.invoice import InvoiceResponse, InvoiceCreate, InvoiceUpdate
from app.services.invoice import InvoiceService
from app.api.dependencies import get_current_user,get_invoice_service
from app.core.exeptions import OrganizationNotFoundError, PermissionDeniedError, InvoiceNotFoundError, \
    CustomerNotFoundError, InvoiceNotEditableError, \
    InvalidInvoiceStatusError, InvoiceHasPendingPaymentError
from app.models import User, Invoice


router = APIRouter(
    prefix="/organization/{organization_id}/invoices",
    tags=["invoice"],
)

@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
        data: InvoiceCreate,
        organization_id:UUID,
        service: InvoiceService = Depends(get_invoice_service),
        user: User = Depends(get_current_user)
)->Invoice:
    try:
        created_invoice = await service.create(
            actor_id=user.id,
            organization_id=organization_id,
            data=data,
        )
        return created_invoice
    except OrganizationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CustomerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

@router.get("/{invoice_id}", response_model=InvoiceResponse, status_code=status.HTTP_200_OK)
async def get_invoice(
        invoice_id: UUID,
        organization_id: UUID,
        service: InvoiceService = Depends(get_invoice_service),
        user: User = Depends(get_current_user)
)->Invoice:
    try:
        invoice = await service.get_invoice(
            actor_id=user.id,
            invoice_id=invoice_id,
            organization_id=organization_id,
        )
        return invoice
    except (OrganizationNotFoundError, InvoiceNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@router.patch(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    status_code=status.HTTP_200_OK,
)
async def update_invoice(
        invoice_id: UUID,
        organization_id: UUID,
        data: InvoiceUpdate,
        service: InvoiceService = Depends(get_invoice_service),
        user: User = Depends(get_current_user)
)->Invoice:
    try:
        updated_invoice = await service.update(
            actor_id=user.id,
            invoice_id=invoice_id,
            organization_id=organization_id,
            data=data,
        )
        return updated_invoice
    except (OrganizationNotFoundError, InvoiceNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvoiceNotEditableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

@router.get("", response_model=list[InvoiceResponse],status_code=status.HTTP_200_OK)
async def get_invoices(
        organization_id: UUID,
        service: InvoiceService = Depends(get_invoice_service),
        user: User = Depends(get_current_user)
)->list[Invoice]:
    try:
        list_invoices = await service.list_invoices(
            actor_id=user.id,
            organization_id=organization_id
        )
        return list_invoices
    except (OrganizationNotFoundError, InvoiceNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@router.post("/{invoice_id}/issue",response_model=InvoiceResponse, status_code=status.HTTP_200_OK)
async def issue_invoice(
        invoice_id: UUID,
        organization_id: UUID,
        service: InvoiceService = Depends(get_invoice_service),
        user: User = Depends(get_current_user)
)->Invoice:
    try:
        updated_invoice = await service.issue_invoice(
            actor_id=user.id,
            invoice_id=invoice_id,
            organization_id=organization_id,
        )
        return updated_invoice
    except (OrganizationNotFoundError, InvoiceNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidInvoiceStatusError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

@router.post("/{invoice_id}/cancel",response_model=InvoiceResponse, status_code=status.HTTP_200_OK)
async def cancel_invoice(
        invoice_id: UUID,
        organization_id: UUID,
        service: InvoiceService = Depends(get_invoice_service),
        user: User = Depends(get_current_user)
)->Invoice:
    try:
        canceled_invoice = await service.cancel_invoice(
            actor_id=user.id,
            invoice_id=invoice_id,
            organization_id=organization_id,
        )
        return canceled_invoice
    except (OrganizationNotFoundError, InvoiceNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (InvalidInvoiceStatusError,InvoiceHasPendingPaymentError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
