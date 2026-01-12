from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ScrapedProduct(BaseModel):
    """Model for scraped product data"""
    name: str
    category: str
    url: str
    price: Optional[float] = None
    rank: Optional[int] = None


class TrendingProduct(BaseModel):
    """Model for trending product with analysis"""
    id: Optional[int] = None
    product_name: str
    category: str
    source_url: str
    trend_score: float
    search_volume: Optional[int] = None
    price_estimate: Optional[float] = None
    first_seen_date: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    status: str = "active"
    notes: Optional[str] = None


class TrendHistory(BaseModel):
    """Model for trend history tracking"""
    id: Optional[int] = None
    product_id: int
    trend_score: float
    search_volume: Optional[int] = None
    recorded_at: Optional[datetime] = None


class TrendAnalysis(BaseModel):
    """Model for trend analysis results"""
    product: TrendingProduct
    search_volume_score: float
    recency_score: float
    price_score: float
    competition_score: float
    final_score: float
