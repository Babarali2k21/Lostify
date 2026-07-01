from pydantic import BaseModel


class SagaStatusResponse(BaseModel):
    sagaName: str
    sagaState: str
    claimId: int
    claimStatus: str
    itemId: int
    itemStatus: str
    matchedItemId: int | None
    notifications: list[str] = []
    steps: list[str] = []
    awsSynced: bool = False
    awsExecutionArn: str | None = None
    awsExecutionStatus: str = "DISABLED"
