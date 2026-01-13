import logging
from typing import Optional, Dict
from pytrends.request import TrendReq
import time

logger = logging.getLogger(__name__)


class GoogleTrendsScraper:
    """Scraper for Google Trends data"""
    
    def __init__(self):
        try:
            # Initialize pytrends with retry support (works with urllib3<2.0)
            self.pytrends = TrendReq(
                hl='en-US',
                tz=360,
                timeout=(10, 25),
                retries=2,
                backoff_factor=0.5
            )
            self.enabled = True
            logger.info("✅ Google Trends initialized successfully")
        except Exception as e:
            logger.warning(f"⚠️ Google Trends initialization failed: {e}")
            self.pytrends = None
            self.enabled = False
    
    def get_trend_data(self, keyword: str) -> Optional[Dict]:
        """Get trend data for a keyword"""
        if not self.enabled or not self.pytrends:
            return None
        
        try:
            # Clean keyword for search
            clean_keyword = self._clean_keyword(keyword)
            
            if not clean_keyword or len(clean_keyword) < 3:
                return None
            
            logger.debug(f"Getting trends for: {clean_keyword}")
            
            # Build payload
            self.pytrends.build_payload(
                kw_list=[clean_keyword],
                cat=0,
                timeframe='today 3-m',  # Last 3 months
                geo='US',
                gprop=''
            )
            
            # Get interest over time
            interest_df = self.pytrends.interest_over_time()
            
            if interest_df is None or interest_df.empty or clean_keyword not in interest_df.columns:
                logger.debug(f"No trend data found for: {clean_keyword}")
                return None
            
            # Calculate metrics
            values = interest_df[clean_keyword].values
            current_value = int(values[-1]) if len(values) > 0 else 0
            avg_value = int(values.mean()) if len(values) > 0 else 0
            max_value = int(values.max()) if len(values) > 0 else 0
            
            # Calculate velocity (rate of change in last month)
            velocity = 0
            if len(values) >= 30:
                recent_avg = values[-30:].mean()
                previous_avg = values[-60:-30].mean() if len(values) >= 60 else values[:-30].mean()
                if previous_avg > 0:
                    velocity = ((recent_avg - previous_avg) / previous_avg) * 100
            
            result = {
                'keyword': clean_keyword,
                'current_volume': current_value,
                'average_volume': avg_value,
                'max_volume': max_value,
                'velocity': round(velocity, 2),
                'has_data': True
            }
            
            logger.info(f"📊 Trend data for '{clean_keyword}': volume={current_value}, velocity={velocity:.1f}%")
            return result
        
        except Exception as e:
            logger.warning(f"Error getting trends for '{keyword}': {e}")
            return None
    
    def _clean_keyword(self, keyword: str) -> str:
        """Clean product name for better search results"""
        if not keyword:
            return ""
        
        # Remove common e-commerce terms
        remove_terms = [
            'pack of', 'set of', 'bundle', 'combo',
            '(', ')', '[', ']', '-', '|', ',',
        ]
        
        cleaned = keyword.lower()
        for term in remove_terms:
            cleaned = cleaned.replace(term, ' ')
        
        # Take first 4 meaningful words
        words = [w for w in cleaned.split() if len(w) > 2][:4]
        result = ' '.join(words)
        
        return result.strip()
    
    def get_related_queries(self, keyword: str) -> Optional[Dict]:
        """Get related queries (bonus feature)"""
        if not self.enabled or not self.pytrends:
            return None
        
        try:
            clean_keyword = self._clean_keyword(keyword)
            
            self.pytrends.build_payload(
                kw_list=[clean_keyword],
                cat=0,
                timeframe='today 3-m',
                geo='US',
                gprop=''
            )
            
            related_queries = self.pytrends.related_queries()
            return related_queries.get(clean_keyword, {})
        
        except Exception as e:
            logger.debug(f"Error getting related queries for '{keyword}': {e}")
            return None
