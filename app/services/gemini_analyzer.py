import logging
from typing import Optional
import google.generativeai as genai
from app.config import settings

logger = logging.getLogger(__name__)


class GeminiAnalyzer:
    """Use Google Gemini AI for product analysis"""
    
    def __init__(self):
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            self.model = genai.GenerativeModel('gemini-pro')
            self.enabled = True
            logger.info("Gemini AI analyzer initialized")
        else:
            self.enabled = False
            logger.warning("Gemini API key not configured, AI features disabled")
    
    async def analyze_product_potential(
        self,
        product_name: str,
        category: str,
        price: Optional[float] = None,
        trend_score: float = 0
    ) -> Optional[str]:
        """Get AI insights about product dropshipping potential"""
        
        if not self.enabled:
            return None
        
        try:
            prompt = f"""As a dropshipping expert, analyze this product:

Product: {product_name}
Category: {category}
Price: ${price if price else 'Unknown'}
Trend Score: {trend_score}/100

Provide a brief analysis (2-3 sentences) covering:
1. Dropshipping viability
2. Target audience
3. Key selling points or concerns

Keep it concise and actionable."""

            response = self.model.generate_content(prompt)
            
            if response and response.text:
                logger.info(f"Gemini analysis generated for: {product_name[:40]}")
                return response.text.strip()
            
        except Exception as e:
            logger.error(f"Gemini API error for '{product_name}': {e}")
        
        return None
    
    async def generate_product_summary(
        self,
        top_products: list
    ) -> Optional[str]:
        """Generate overall trend summary"""
        
        if not self.enabled or not top_products:
            return None
        
        try:
            products_text = "\n".join([
                f"{i+1}. {p.product_name} (Score: {p.trend_score}, Category: {p.category})"
                for i, p in enumerate(top_products[:5])
            ])
            
            prompt = f"""Analyze these top trending dropshipping products:

{products_text}

Provide a brief market insight (2-3 sentences) about the overall trends you see."""

            response = self.model.generate_content(prompt)
            
            if response and response.text:
                return response.text.strip()
            
        except Exception as e:
            logger.error(f"Gemini summary error: {e}")
        
        return None
