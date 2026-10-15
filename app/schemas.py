from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal

class RawFeedback(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    source: str = Field(min_length=1, max_length=40)
    external_id: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=30)
    url: str | None = None
    author: str | None = None
    title: str | None = None
    text: str = Field(min_length=1, max_length=100000)
    published_at: datetime | None = None
    engagement: int = 0

class Classification(BaseModel):
    relevant: bool
    relevance: float = Field(ge=0, le=1)
    platform: str = "Other"
    user_type: str = "Unknown"
    product_area: str = "Other"
    feature: str | None = None
    feedback_type: str = "Other"
    sentiment: Literal["Positive", "Neutral", "Negative", "Mixed"] = "Neutral"
    severity: Literal["Low", "Medium", "High", "Critical"] = "Low"
    summary: str
    requested_change: str | None = None
    competitor: str | None = None
