import logging
from typing import List, Optional
from datetime import datetime
from app.models import ScrapedProduct, TrendingProduct, TrendHistory
from app.scrapers.google_trends import GoogleTrendsScraper
from app.services.gemini_analyzer import GeminiAnalyzer
from app.config import settings
import time
import random

logger = logging.getLogger(__name__)


class TrendAnalyzer:
    """Analyzes scraped products and calculates trend scores"""
    
    def __init__(self):
        self.google_trends = GoogleTrendsScraper()
        self.gemini_analyzer = GeminiAnalyzer()
    
    def calculate_trend_score(
        self,
        product: ScrapedProduct,
        trend_data: Optional[dict]
    ) -> float:
        """
        Calculate trend score (0-100) based on multiple factors
        
        Weights:
        - Search volume increase rate: 40%
        - Recency of trend: 30%
        - Price point viability: 20%
        - Competition estimate: 10%
        """
        score = 0.0
        
        # 1. Search Volume Velocity Score (40 points)
        if trend_data and trend_data.get('has_data'):
            velocity = trend_data.get('velocity', 0)
            volume = trend_data.get('current_volume', 0)
            
            # Velocity component (up to 25 points)
            if velocity > 100:
                velocity_score = 25
            elif velocity > 50:
                velocity_score = 20
            elif velocity > 20:
                velocity_score = 15
            elif velocity > 0:
                velocity_score = 10
            else:
                velocity_score = 5
            
            # Volume component (up to 15 points)
            if volume > 75:
                volume_score = 15
            elif volume > 50:
                volume_score = 12
            elif volume > 25:
                volume_score = 8
            elif volume > 10:
                volume_score = 5
            else:
                volume_score = 2
            
            score += velocity_score + volume_score
        else:
            # No trend data - use neutral score based on being a bestseller
            score += 15
        
        # 2. Recency Score (30 points)
        # Products in best sellers are by definition recent
        # Higher rank (lower number) = more recent/popular
        if product.rank:
            if product.rank <= 10:
                score += 30
            elif product.rank <= 25:
                score += 25
            elif product.rank <= 50:
                score += 20
            else:
                score += 15
        else:
            score += 20  # Default for products without rank
        
        # 3. Price Point Viability (20 points)
        # Ideal dropshipping range: $15-$150
        if product.price:
            if 15 <= product.price <= 150:
                # Sweet spot
                if 25 <= product.price <= 75:
                    score += 20
                else:
                    score += 15
            elif 10 <= product.price < 15 or 150 < product.price <= 200:
                # Acceptable but not ideal
                score += 10
            else:
                # Too cheap or too expensive
                score += 5
        else:
            score += 10  # Neutral if no price data
        
        # 4. Competition Estimate (10 points)
        # Based on search volume (higher volume = more competition)
        if trend_data and trend_data.get('has_data'):
            volume = trend_data.get('current_volume', 0)
            
            # Lower competition is better
            if volume < 30:
                comp_score = 10  # Low competition
            elif volume < 60:
                comp_score = 7   # Medium competition
            elif volume < 85:
                comp_score = 4   # High competition
            else:
                comp_score = 2   # Very high competition
            
            score += comp_score
        else:
            score += 7  # Neutral competition score
        
        # Ensure score is between 0 and 100
        return min(max(score, 0), 100)
    
    async def analyze_products(
        self,
        products: List[ScrapedProduct]
    ) -> List[TrendingProduct]:
        """Analyze all scraped products and return trending ones"""
        
        trending_products = []
        
        logger.info(f"Analyzing {len(products)} products...")
        
        # Only query Google Trends for top 15 products (by rank) to avoid rate limits
        # Sort by rank first, then process
        sorted_products = sorted(products, key=lambda p: p.rank if p.rank else 999)
        products_for_trends = sorted_products[:15]  # Top 15 get trend data
        products_without_trends = sorted_products[15:]
        
        logger.info(f"📊 Getting Google Trends for top {len(products_for_trends)} products...")
        
        # Process products that will get trend data
        for idx, product in enumerate(products_for_trends, 1):
            try:
                # Get Google Trends data with longer delay
                trend_data = self.google_trends.get_trend_data(product.name)
                
                # Longer random delay (8-15 seconds) to avoid rate limiting
                delay = random.uniform(8, 15)
                logger.debug(f"Waiting {delay:.1f}s before next trend query...")
                time.sleep(delay)
                
                # Calculate trend score
                trend_score = self.calculate_trend_score(product, trend_data)
                
                # Get AI insights for top products
                ai_notes = None
                if trend_score >= 60 and self.gemini_analyzer.enabled:
                    ai_notes = await self.gemini_analyzer.analyze_product_potential(
                        product_name=product.name,
                        category=product.category,
                        price=product.price,
                        trend_score=trend_score
                    )
                
                # Create TrendingProduct
                base_notes = f"Velocity: {trend_data.get('velocity', 0)}%" if trend_data else "Bestseller rank bonus"
                notes = f"{base_notes}\n\n🤖 AI Insight: {ai_notes}" if ai_notes else base_notes
                
                trending_product = TrendingProduct(
                    product_name=product.name,
                    category=product.category,
                    source_url=product.url,
                    trend_score=round(trend_score, 2),
                    search_volume=trend_data.get('current_volume', 0) if trend_data else 0,
                    price_estimate=product.price,
                    notes=notes
                )
                
                trending_products.append(trending_product)
                
                logger.info(
                    f"[{idx}/{len(products_for_trends)}] {product.name[:40]}... - "
                    f"Score: {trend_score:.1f}, "
                    f"Volume: {trending_product.search_volume}"
                )
                
            except Exception as e:
                logger.error(f"Error analyzing product '{product.name}': {e}")
                continue
        
        # Process remaining products without Google Trends (faster)
        logger.info(f"⚡ Processing {len(products_without_trends)} additional products (no trend lookup)...")
        
        for idx, product in enumerate(products_without_trends, 1):
            try:
                # Calculate score without trend data
                trend_score = self.calculate_trend_score(product, None)
                
                trending_product = TrendingProduct(
                    product_name=product.name,
                    category=product.category,
                    source_url=product.url,
                    trend_score=round(trend_score, 2),
                    search_volume=0,
                    price_estimate=product.price,
                    notes="Bestseller item"
                )
                
                trending_products.append(trending_product)
                
            except Exception as e:
                logger.error(f"Error analyzing product '{product.name}': {e}")
                continue
        
        # Sort by trend score
        trending_products.sort(key=lambda x: x.trend_score, reverse=True)
        
        logger.info(f"Analysis complete. Top score: {trending_products[0].trend_score if trending_products else 0}")
        
        return trending_products
    
    def get_hot_products(
        self,
        products: List[TrendingProduct],
        threshold: float = 70.0
    ) -> List[TrendingProduct]:
        """Filter products with score above threshold"""
        hot_products = [p for p in products if p.trend_score >= threshold]
        logger.info(f"Found {len(hot_products)} hot products (score >= {threshold})")
        return hot_products
