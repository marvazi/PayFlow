from uuid import UUID
from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from sqlalchemy.ext.asyncio import result
from starlette import status
from starlette.responses import Response

from app.schemas.invoice import InvoiceResponse, InvoiceCreate
from app.schemas.membership import MembershipCreate, MembershipResponse,MembershipUpdate
from app.services.invoice import InvoiceService
from app.services.membership import MembershipService
from app.api.dependencies import get_current_user, get_organization_service, get_member_service, get_invoice_service
from app.core.exeptions import OrganizationNotFoundError, \
    MembershipAlreadyExistsError, UserNotFoundError, PermissionDeniedError, InvalidMembershipRoleError, \
    MembershipNotFoundError, InvoiceNotFoundError, CustomerNotFoundError
from app.models import User, Invoice
from app.schemas.organization import OrganizationResponse, OrganizationCreate
from app.services.organization import OrganizationService


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