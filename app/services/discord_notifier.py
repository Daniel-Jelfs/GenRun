import logging
from typing import List
import httpx
from app.models import TrendingProduct
from app.config import settings

logger = logging.getLogger(__name__)


class DiscordNotifier:
    """Send notifications to Discord via webhook"""
    
    def __init__(self):
        self.webhook_url = settings.discord_webhook_url
    
    async def send_trend_summary(
        self,
        products: List[TrendingProduct],
        hot_count: int = 0
    ) -> bool:
        """Send summary of detected trends"""
        
        if not self.webhook_url:
            logger.warning("Discord webhook URL not configured")
            return False
        
        try:
            # Get top 10 products
            top_products = sorted(products, key=lambda x: x.trend_score, reverse=True)[:10]
            
            # Calculate stats
            highest_score = top_products[0].trend_score if top_products else 0
            avg_score = sum(p.trend_score for p in products) / len(products) if products else 0
            
            # Build embed
            embed = {
                "title": "🔥 Daily Dropshipping Trend Report",
                "description": f"Found **{len(products)}** trending products\n"
                               f"Hot products (score ≥70): **{hot_count}**\n"
                               f"Highest score: **{highest_score:.1f}/100**\n"
                               f"Average score: **{avg_score:.1f}/100**",
                "color": 0xFF6B35 if hot_count > 0 else 0x4ECDC4,
                "fields": [],
                "footer": {
                    "text": "Dropshipping Trend Detector"
                },
                "timestamp": products[0].last_updated.isoformat() if products else None
            }
            
            # Add top 5 products as fields
            for idx, product in enumerate(top_products[:5], 1):
                emoji = "🔥" if product.trend_score >= 70 else "📈"
                price_str = f"${product.price_estimate:.2f}" if product.price_estimate else "N/A"
                
                field_value = (
                    f"**Score:** {product.trend_score:.1f}/100\n"
                    f"**Category:** {product.category}\n"
                    f"**Price:** {price_str}\n"
                    f"**Search Volume:** {product.search_volume}\n"
                    f"[View on Amazon]({product.source_url})"
                )
                
                embed["fields"].append({
                    "name": f"{emoji} #{idx} - {product.product_name[:80]}",
                    "value": field_value,
                    "inline": False
                })
            
            # Send webhook
            payload = {
                "embeds": [embed],
                "username": "Trend Detective",
                "avatar_url": "https://cdn-icons-png.flaticon.com/512/2936/2936886.png"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10
                )
                
                if response.status_code == 204:
                    logger.info("Discord notification sent successfully")
                    return True
                else:
                    logger.error(f"Discord webhook failed: {response.status_code}")
                    return False
        
        except Exception as e:
            logger.error(f"Error sending Discord notification: {e}")
            return False
    
    async def send_error_notification(self, error_message: str) -> bool:
        """Send error notification"""
        
        if not self.webhook_url:
            return False
        
        try:
            embed = {
                "title": "⚠️ Trend Detection Error",
                "description": f"An error occurred during trend detection:\n\n```{error_message}```",
                "color": 0xFF0000,
                "footer": {
                    "text": "Dropshipping Trend Detector"
                }
            }
            
            payload = {
                "embeds": [embed],
                "username": "Trend Detective"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10
                )
                
                return response.status_code == 204
        
        except Exception as e:
            logger.error(f"Error sending error notification: {e}")
            return False
