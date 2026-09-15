from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from starlette import status
from app.services.user import UserService
from app.api.dependencies import get_user_service, get_current_user, get_organization_service
from app.core.exeptions import EmailAlreadyExistsError, InvalidCredentialsError, OrganizationNotFoundError
from app.models import User, Organization
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