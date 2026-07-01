from pydantic import BaseModel, EmailStr, Field

from .models import ItemStatus, ItemType


class ItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    item_type: ItemType


class ItemResponse(BaseModel):
    id: int
    title: str
    description: str
    item_type: ItemType
    status: ItemStatus
    owner_user_id: int
    matched_item_id: int | None

    model_config = {"from_attributes": True}


class UserRegister(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    username: str

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
