from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from starlette import status

from app.api.dependencies import get_user_service
from app.core.exeptions import EmailAlreadyExistsError
from app.schemas.user import UserCreate, UserResponse
from app.services.user import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register",status_code=status.HTTP_201_CREATED,response_model=UserResponse)
async def register_user(
        user:UserCreate,
        user_service:UserService = Depends(get_user_service),
):
    try:
        created_user = await user_service.register(user)
    except EmailAlreadyExistsError  as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Пользователь с таким email уже существует') from exc
    return created_user
