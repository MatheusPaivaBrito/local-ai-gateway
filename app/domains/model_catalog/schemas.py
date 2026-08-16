from pydantic import BaseModel, Field


class PullModelRequest(BaseModel):
    model: str = Field(min_length=1, max_length=200)
