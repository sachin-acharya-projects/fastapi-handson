from fastapi import APIRouter
from fastapi_pagination import Page, paginate
from pydantic import UUID4

from app.api.deps.user import UserServiceDep
from app.schemas.user import (
    UserCreationModel,
    UserResponseModel,
    UserUpdateModel,
    to_user_response,
)

router = APIRouter()


@router.post("/")
def create_user(
    payload: UserCreationModel,
    service: UserServiceDep,
) -> UserResponseModel:
    user = service.create_user(payload)
    return to_user_response(user)


@router.get("/")
def list_users(
    service: UserServiceDep,
) -> Page[UserResponseModel]:
    users = service.list_users()
    return paginate([to_user_response(user) for user in users])


@router.get("/{user_id}")
def retrieve_user(
    user_id: UUID4,
    service: UserServiceDep,
) -> UserResponseModel:
    user = service.retrieve_user(user_id)
    return to_user_response(user)


@router.patch("/{user_id}")
def update_user(
    user_id: UUID4,
    payload: UserUpdateModel,
    service: UserServiceDep,
) -> UserResponseModel | None:
    user = service.update_user(user_id, payload)
    return to_user_response(user) if user else None


@router.delete("/{user_id}")
def delete_user(
    user_id: UUID4,
    service: UserServiceDep,
) -> dict[str, str]:
    service.delete_user(user_id)
    return {"message": "success"}
