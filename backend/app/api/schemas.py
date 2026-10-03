from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime, date
from typing import Literal
from app.utils import normalize_instagram_username


class HealthResponse(BaseModel):
    status: str
    service: str


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None


class TargetAccountRequest(BaseModel):
    """Request model for target account"""
    username: str = Field(..., min_length=1, max_length=30)
    label: str = Field(default="", max_length=50)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v):
        return normalize_instagram_username(v)


class AccountMatchResponse(BaseModel):
    """Match result for a post in a specific account"""
    username: str
    label: str
    status: str
    similarity: float
    visual_similarity: float | None
    caption_similarity: float
    candidate_permalink: str | None = None


class PostResultResponse(BaseModel):
    """Audit result for a single post"""
    original: dict = Field(description="Master post data: shortcode, permalink, published_at, caption, type")
    accounts: list[AccountMatchResponse] = Field(description="Match results per account")


class ScanRequest(BaseModel):
    """Request model for running an audit scan"""
    master_username: str = Field(..., min_length=1, max_length=30)
    master_label: str = Field(default="Principal", max_length=50)
    targets: list[TargetAccountRequest] = Field(..., min_length=1, max_length=10)
    scan_mode: Literal["count", "date"] = Field(default="date")
    limit: int | None = Field(default=None, ge=1, le=100)
    from_date: date | None = Field(default=None)
    to_date: date | None = Field(default=None)

    @field_validator("master_username")
    @classmethod
    def validate_master(cls, v):
        return normalize_instagram_username(v)

    @field_validator("limit")
    @classmethod
    def validate_limit_for_mode(cls, v, info):
        scan_mode = info.data.get("scan_mode")
        if scan_mode == "count" and v is None:
            raise ValueError("limit required for count mode")
        if scan_mode == "date" and v is not None:
            # limit ignored in date mode, but allow it for backward compatibility
            pass
        return v

    @field_validator("from_date")
    @classmethod
    def validate_from_date_for_mode(cls, v, info):
        scan_mode = info.data.get("scan_mode")
        if scan_mode == "date" and v is None:
            raise ValueError("from_date required for date mode")
        return v

    @field_validator("to_date")
    @classmethod
    def validate_date_range(cls, v, info):
        from_date = info.data.get("from_date")
        scan_mode = info.data.get("scan_mode")

        if scan_mode == "date":
            if v is None:
                # Default to today
                return date.today()
            if from_date and from_date > v:
                raise ValueError("from_date must be before or equal to to_date")

        return v

    @model_validator(mode="after")
    def validate_scan_mode_requirements(self):
        """Validate cross-field requirements based on scan_mode"""
        if self.scan_mode == "count":
            if self.limit is None:
                raise ValueError("limit is required for count mode")
            if not (1 <= self.limit <= 100):
                raise ValueError("limit must be between 1 and 100")
        elif self.scan_mode == "date":
            if self.from_date is None:
                raise ValueError("from_date is required for date mode")
            if self.to_date is None:
                self.to_date = date.today()
            if self.from_date > self.to_date:
                raise ValueError("from_date must be before or equal to to_date")
            if self.to_date > date.today():
                raise ValueError("to_date cannot be in the future")
        return self


class ScanResponse(BaseModel):
    """Response model for completed scan"""
    scan_id: str
    status: str
    master_account: str
    master_posts: int
    regional_posts: dict[str, int]
    found_everywhere: int
    with_missing: int
    with_review: int
    missing_by_account: dict[str, int]
    review_by_account: dict[str, int]
    export_url: str
    posts: list[PostResultResponse] = Field(default_factory=list, description="Detailed results per post")
    scan_mode: str = Field(default="count")
    scan_period: str = Field(default="", description="Human readable period: '01/01/2025 - 02/10/2026' or 'Últimas 20 publicaciones'")
    warnings: list[str] = Field(default_factory=list, description="Warnings about scan completeness or data quality")
    coverage_by_account: dict = Field(default_factory=dict, description="Coverage details per account (date mode only)")
