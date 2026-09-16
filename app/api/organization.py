from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from starlette import status

from app.db.session import get_session
from app.schemas.membership import MembershipCreate, MembershipResponse
from app.services.membership import MembershipService
from app.services.user import UserService
from app.api.dependencies import get_user_service, get_current_user, get_organization_service, get_member_service
from app.core.exeptions import EmailAlreadyExistsError, InvalidCredentialsError, OrganizationNotFoundError, \
    MembershipAlreadyExistsError, UserNotFoundError, PermissionDeniedError, InvalidMembershipRoleError
from app.models import User, Organization, organization
from app.schemas.organization import OrganizationResponse, OrganizationCreate
from app.schemas.user import UserCreate, UserResponse, TokenResponse, UserLogin
from app.services.organization import OrganizationService
from app.services.user import UserService
from app.core.security import create_access_token


router = APIRouter(prefix="/organization", tags=["organization"])


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
        organization_create: OrganizationCreate,
        user: User = Depends(get_current_user),
        organization_service: OrganizationService = Depends(get_organization_service),

):
    created_organization = await organization_service.create(name=organization_create.name,user_id=user.id)
    return created_organization

@router.get("", response_model=list[OrganizationResponse], status_code=status.HTTP_200_OK)
async def get_organization(
        user:User = Depends(get_current_user),
        organization_service: OrganizationService = Depends(get_organization_service),
):
    list_organizations = await organization_service.get_by_user_id(user_id=user.id)
    return list_organizations

@router.get("/{organization_id}", response_model=OrganizationResponse, status_code=status.HTTP_200_OK)
async def get_organization_by_id(
        organization_id:UUID,
        user: User = Depends(get_current_user),
        organization_service: OrganizationService = Depends(get_organization_service),
):
    try:
        organization = await organization_service.get_organization_by_id(organization_id=organization_id, user_id=user.id)
    except OrganizationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Организация не найдена") from exc
    return organization

@router.post("/{organization_id}/members", response_model=MembershipResponse, status_code=status.HTTP_201_CREATED)
async def create_member(
        organization_id: UUID,
        member:MembershipCreate,
        user: User = Depends(get_current_user),
        member_service: MembershipService = Depends(get_member_service)
):
    try:
        added_member = await member_service.add_member(
            actor_id=user.id,
            organization_id=organization_id,
            new_user_id=member.user_id,
            role=member.role,
        )
    except (OrganizationNotFoundError, UserNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except MembershipAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidMembershipRoleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return added_member