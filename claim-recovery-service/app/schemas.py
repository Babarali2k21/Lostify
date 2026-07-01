from pydantic import BaseModel

from .models import ClaimStatus


class ClaimCreate(BaseModel):
    item_id: int


class ClaimResponse(BaseModel):
    id: int
    item_id: int
    claimant_user_id: int
    status: ClaimStatus

    model_config = {"from_attributes": True}
