from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from starlette import status

from app.api.dependencies import get_user_service, get_current_user
from app.core.exeptions import EmailAlreadyExistsError, InvalidCredentialsError
from app.models import User
from app.schemas.user import UserCreate, UserResponse, TokenResponse, UserLogin
from app.services.user import UserService
from app.core.security import create_access_token

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

@router.post("/login",response_model=TokenResponse,status_code=status.HTTP_200_OK)
async def login_user(
        user: UserLogin,
        user_service: UserService = Depends(get_user_service),
)-> TokenResponse:
    try:
        authenticated_user = await user_service.authenticate(user)
        token = create_access_token(authenticated_user.id)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Неверный email или пароль',
            headers={"WWW-Authenticate": "Bearer"}
        ) from exc
    return TokenResponse(
        access_token=token,
    )
@router.get("/me",response_model=UserResponse)
async def read_me(current_user:User = Depends(get_current_user)):
    return current_user
