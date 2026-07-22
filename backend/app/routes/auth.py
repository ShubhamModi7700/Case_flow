from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import (
    authenticate_user,
    get_current_user,
)
from app.database import get_db

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/login",
    response_model=schemas.LoginResponse,
)
def login(
    login_data: schemas.LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = authenticate_user(
        db=db,
        email=login_data.email,
        password=login_data.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    request.session.clear()
    request.session["user_id"] = user.id

    return {
        "message": "Login successful",
        "user": user,
    }


@router.post("/logout")
def logout(request: Request):
    request.session.clear()

    return {
        "message": "Logout successful",
    }


@router.get(
    "/me",
    response_model=schemas.CurrentUserResponse,
)
def get_my_profile(
    current_user: models.User = Depends(
        get_current_user
    ),
):
    return current_user