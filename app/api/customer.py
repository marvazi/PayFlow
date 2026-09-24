from uuid import UUID
from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from sqlalchemy.ext.asyncio import result
from starlette import status
from starlette.responses import Response

from app.schemas.customer import CustomerResponse, CustomerCreate, CustomerUpdate
from app.schemas.membership import MembershipCreate, MembershipResponse,MembershipUpdate
from app.services.customer import CustomerService
from app.services.membership import MembershipService
from app.api.dependencies import get_current_user, get_organization_service, get_member_service, get_customer_service
from app.core.exeptions import OrganizationNotFoundError, \
    MembershipAlreadyExistsError, UserNotFoundError, PermissionDeniedError, InvalidMembershipRoleError, \
    MembershipNotFoundError, CustomerAlreadyExistsError, CustomerNotFoundError
from app.models import User
from app.schemas.organization import OrganizationResponse, OrganizationCreate
from app.services.organization import OrganizationService




router = APIRouter(prefix="/organization/{organization_id}/customers", tags=["customer"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CustomerResponse)
async def create_customer(
        data: CustomerCreate,
        organization_id: UUID,
        customer_service: CustomerService = Depends(get_customer_service),
        user: User = Depends(get_current_user),

):
    try:
        created_customer = await customer_service.create_customer(data=data,actor_id=user.id, organization_id=organization_id)
        return created_customer
    except OrganizationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CustomerAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[CustomerResponse],status_code=status.HTTP_200_OK)
async def get_customers(
        organization_id: UUID,
        customer_service: CustomerService = Depends(get_customer_service),
        user: User = Depends(get_current_user),
):
    try:
        customers = await customer_service.list_customers(organization_id=organization_id, actor_id=user.id)
    except OrganizationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return customers

@router.get("/{customer_id}", response_model=CustomerResponse,status_code=status.HTTP_200_OK)
async def get_customer(
        organization_id: UUID,
        customer_id: UUID,
        customer_service: CustomerService = Depends(get_customer_service),
        user: User = Depends(get_current_user),
):
    try:
        customer = await customer_service.find_customer_by_id(
        actor_id=user.id,
        organization_id=organization_id,
        customer_id=customer_id
    )
    except (OrganizationNotFoundError,CustomerNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CustomerAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return customer

@router.patch("/{customer_id}", status_code=status.HTTP_200_OK,response_model=CustomerResponse)
async def update_customer(
        data: CustomerUpdate,
        organization_id: UUID,
        customer_id: UUID,
        customer_service: CustomerService = Depends(get_customer_service),
        user: User = Depends(get_current_user),
):
    try:
        updated_customer = await customer_service.update_customer(
            data=data,
            actor_id=user.id,
            organization_id=organization_id,
            customer_id=customer_id
        )
        return updated_customer
    except (OrganizationNotFoundError, CustomerNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CustomerAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
        organization_id: UUID,
        customer_id: UUID,
        customer_service: CustomerService = Depends(get_customer_service),
        user: User = Depends(get_current_user),
):
    try:
        await customer_service.delete_customer(
            actor_id=user.id,
            organization_id=organization_id,
            customer_id=customer_id
        )
    except (OrganizationNotFoundError, CustomerNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)