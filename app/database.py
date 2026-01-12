from supabase import create_client, Client
from app.config import settings
from app.models import TrendingProduct, TrendHistory
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class Database:
    """Database operations for Supabase"""
    
    def __init__(self):
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_key
        )
    
    async def init_tables(self):
        """Initialize database tables if they don't exist"""
        try:
            # Check if tables exist by attempting a simple query
            self.client.table('trending_products').select("id").limit(1).execute()
            logger.info("Database tables already exist")
        except Exception as e:
            logger.warning(f"Tables might not exist: {e}")
            # Note: Table creation should be done via Supabase dashboard
            # SQL provided in README.md
    
    def insert_trending_product(self, product: TrendingProduct) -> Optional[dict]:
        """Insert a new trending product"""
        try:
            data = product.model_dump(exclude={'id'}, exclude_none=True)
            response = self.client.table('trending_products').insert(data).execute()
            logger.info(f"Inserted product: {product.product_name}")
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error inserting product {product.product_name}: {e}")
            return None
    
    def update_trending_product(self, product_id: int, product: TrendingProduct) -> Optional[dict]:
        """Update an existing trending product"""
        try:
            data = product.model_dump(exclude={'id', 'first_seen_date'}, exclude_none=True)
            response = self.client.table('trending_products')\
                .update(data)\
                .eq('id', product_id)\
                .execute()
            logger.info(f"Updated product ID: {product_id}")
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error updating product {product_id}: {e}")
            return None
    
    def get_product_by_name(self, name: str) -> Optional[dict]:
        """Get product by name"""
        try:
            response = self.client.table('trending_products')\
                .select("*")\
                .eq('product_name', name)\
                .execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching product {name}: {e}")
            return None
    
    def insert_trend_history(self, history: TrendHistory) -> Optional[dict]:
        """Insert trend history record"""
        try:
            data = history.model_dump(exclude={'id'}, exclude_none=True)
            response = self.client.table('trend_history').insert(data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error inserting trend history: {e}")
            return None
    
    def get_top_trending_products(self, limit: int = 10) -> List[dict]:
        """Get top trending products by score"""
        try:
            response = self.client.table('trending_products')\
                .select("*")\
                .eq('status', 'active')\
                .order('trend_score', desc=True)\
                .limit(limit)\
                .execute()
            return response.data
        except Exception as e:
            logger.error(f"Error fetching top products: {e}")
            return []
    
    def archive_old_products(self, days: int = 30):
        """Archive products older than specified days with low scores"""
        try:
            from datetime import datetime, timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            response = self.client.table('trending_products')\
                .update({'status': 'archived'})\
                .lt('last_updated', cutoff_date.isoformat())\
                .lt('trend_score', 50)\
                .execute()
            
            logger.info(f"Archived {len(response.data) if response.data else 0} old products")
        except Exception as e:
            logger.error(f"Error archiving products: {e}")


db = Database()
