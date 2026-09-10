from pydantic import BaseModel, Field, field_validator, HttpUrl
import validators
from typing import Optional
from decimal import Decimal
from ..models import StoreEnum, StatusEnum

class ScrapedOffer(BaseModel):
    fig_name: str = Field(..., min_length=3)
    price: Optional[Decimal] = None
    link: HttpUrl
    code: Optional[str] = None
    series_title: Optional[str] = None
    manufacturer: Optional[str] = None
    status: StatusEnum
    scale: Optional[str] = None
    store: StoreEnum
    ch_name: str = Field(..., min_length=2)


class Figure(BaseModel):
    F_ID: int = Field(..., description="Figure ID", title="Figure ID")
    C_ID: int = Field(..., description="Character ID", title="Character ID")
    name: str = Field(..., max_length=100)
    code: Optional[str] = Field(None, max_length=100)
    manufacturer: Optional[str] = Field(None, max_length=50)
    scale: Optional[str] = Field(None, max_length=20)

class Offer(BaseModel):
    O_ID: int = Field(..., description="Offer ID", title="Offer ID")
    F_ID: int = Field(..., description="Figure ID", title="Figure ID")
    link: str = Field(..., max_length=500)
    @field_validator("link")
    @classmethod
    def link_validator(cls, v):
        if validators.domain(v):
            v="https://"+v
        if not validators.url(v):
            raise ValueError("Link must be valid URL")
        return v
    store: StoreEnum = Field(..., description="Store")
    price: Decimal = Field(..., description="Price")
    @field_validator("price")
    @classmethod
    def price_validator(cls, v):
        return round(v, 2)
    status: StatusEnum = Field(default=StatusEnum.AVAILABLE, description="Status")

class Series(BaseModel):
    S_ID: int = Field(..., description="Series ID")
    title: str = Field(..., max_length=100, description="Series title")

class Character(BaseModel):
    C_ID: int = Field(..., description="Character ID")
    S_ID: int = Field(..., description="Series ID")
    name: str = Field(..., max_length=100)