import logging
from typing import Optional, Dict
import time
import requests

logger = logging.getLogger(__name__)


class GoogleTrendsScraper:
    """Scraper for Google Trends data - Fixed for urllib3 compatibility"""
    
    def __init__(self):
        self.pytrends = None
        self._init_pytrends()
    
    def _init_pytrends(self):
        """Initialize pytrends with compatibility fix"""
        try:
            from pytrends.request import TrendReq
            
            # Create a custom session without the problematic retry parameters
            session = requests.Session()
            
            # Initialize without retries parameter (causes urllib3 compatibility issues)
            self.pytrends = TrendReq(
                hl='en-US',
                tz=360,
                timeout=(10, 25),
                requests_args={'verify': True}
            )
            logger.info("Google Trends initialized successfully")
        except Exception as e:
            logger.warning(f"Could not initialize Google Trends: {e}")
            self.pytrends = None
    
    def get_trend_data(self, keyword: str) -> Optional[Dict]:
        """Get trend data for a keyword"""
        if not self.pytrends:
            return self._get_fallback_data(keyword)
        
        try:
            # Clean keyword for search
            clean_keyword = self._clean_keyword(keyword)
            
            if not clean_keyword or len(clean_keyword) < 3:
                return None
            
            logger.debug(f"Getting trends for: {clean_keyword}")
            
            # Build payload with error handling
            try:
                self.pytrends.build_payload(
                    kw_list=[clean_keyword],
                    cat=0,
                    timeframe='today 3-m',  # Last 3 months
                    geo='US',
                    gprop=''
                )
            except Exception as e:
                logger.debug(f"Payload build failed for '{clean_keyword}': {e}")
                return self._get_fallback_data(keyword)
            
            # Get interest over time
            try:
                interest_df = self.pytrends.interest_over_time()
            except Exception as e:
                logger.debug(f"Interest over time failed for '{clean_keyword}': {e}")
                return self._get_fallback_data(keyword)
            
            if interest_df is None or interest_df.empty or clean_keyword not in interest_df.columns:
                logger.debug(f"No trend data found for: {clean_keyword}")
                return self._get_fallback_data(keyword)
            
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
            
            logger.info(f"Trend data for '{clean_keyword}': volume={current_value}, velocity={velocity:.1f}%")
            return result
        
        except Exception as e:
            logger.debug(f"Error getting trends for '{keyword}': {e}")
            return self._get_fallback_data(keyword)
    
    def _get_fallback_data(self, keyword: str) -> Dict:
        """Return fallback data when Google Trends is unavailable"""
        # Generate pseudo-random but consistent scores based on keyword
        # This ensures the app still works when Google Trends is down
        clean_keyword = self._clean_keyword(keyword)
        
        # Simple hash-based pseudo-randomness for consistency
        hash_val = sum(ord(c) for c in clean_keyword) if clean_keyword else 0
        
        # Generate values between 20-80 based on hash
        base_volume = 30 + (hash_val % 50)
        velocity = -10 + (hash_val % 30)  # -10 to +20
        
        return {
            'keyword': clean_keyword,
            'current_volume': base_volume,
            'average_volume': base_volume - 5,
            'max_volume': base_volume + 10,
            'velocity': round(velocity, 2),
            'has_data': False  # Mark as fallback data
        }
    
    def _clean_keyword(self, keyword: str) -> str:
        """Clean product name for better search results"""
        if not keyword:
            return ""
        
        # Remove common e-commerce terms and special characters
        remove_terms = [
            'pack of', 'set of', 'bundle', 'combo', 'pack', 'count',
            '(', ')', '[', ']', '-', '|', ',', '.', '/', '\\',
            'oz', 'fl', 'ml', 'inch', 'inches', '"', "'",
            'amazon', 'best seller', 'top rated'
        ]
        
        cleaned = keyword.lower()
        for term in remove_terms:
            cleaned = cleaned.replace(term, ' ')
        
        # Remove numbers at the start
        import re
        cleaned = re.sub(r'^\d+\s*', '', cleaned)
        
        # Take first 4 meaningful words (shorter = better for trends)
        words = [w for w in cleaned.split() if len(w) > 2 and not w.isdigit()][:4]
        result = ' '.join(words)
        
        return result.strip()
    
    def get_related_queries(self, keyword: str) -> Optional[Dict]:
        """Get related queries (bonus feature)"""
        if not self.pytrends:
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
