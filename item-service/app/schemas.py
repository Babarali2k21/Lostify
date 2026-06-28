from pydantic import BaseModel, Field

from .models import ClaimStatus, ItemStatus, ItemType


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


class ClaimCreate(BaseModel):
    item_id: int


class ClaimResponse(BaseModel):
    id: int
    item_id: int
    claimant_user_id: int
    status: ClaimStatus

    model_config = {"from_attributes": True}


class MatchResponse(BaseModel):
    lost_item_id: int
    found_item_id: int
    message: str
