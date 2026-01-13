import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from typing import List
import asyncio

from app.config import settings
from app.database import db
from app.models import TrendingProduct, TrendHistory, ScrapedProduct
from app.scrapers.amazon_scraper import AmazonScraper
from app.services.trend_analyzer import TrendAnalyzer
from app.services.discord_notifier import DiscordNotifier

logger = logging.getLogger(__name__)

# Global region setting
current_region = "US"


class TrendDetectionScheduler:
    """Scheduler for daily trend detection jobs"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.trend_analyzer = TrendAnalyzer()
        self.discord_notifier = DiscordNotifier()
    
    def get_region(self) -> str:
        """Get current region"""
        global current_region
        return current_region
    
    def set_region(self, region: str):
        """Set region for scraping"""
        global current_region
        if region.upper() in ["US", "UK"]:
            current_region = region.upper()
            logger.info(f"Region set to: {current_region}")
    
    async def run_trend_detection(self, region: str = None):
        """Main trend detection job"""
        global current_region
        
        if region:
            current_region = region.upper()
        
        start_time = datetime.utcnow()
        logger.info("="*60)
        logger.info(f"Starting trend detection job at {start_time.isoformat()}")
        logger.info(f"Region: {current_region}")
        logger.info("="*60)
        
        try:
            # Create scraper for current region
            amazon_scraper = AmazonScraper(region=current_region)
            
            # Step 1: Scrape Amazon Best Sellers
            logger.info("Step 1: Scraping Amazon Best Sellers...")
            scraped_data = amazon_scraper.scrape_all_categories(products_per_category=50)
            
            if not scraped_data:
                error_msg = f"No products scraped from Amazon {current_region}"
                logger.error(error_msg)
                await self.discord_notifier.send_error_notification(error_msg)
                return
            
            # Convert dict data to ScrapedProduct objects
            scraped_products = []
            for item in scraped_data:
                try:
                    product = ScrapedProduct(
                        name=item['name'],
                        category=item['category'],
                        url=item['url'],
                        price=item.get('price'),
                        rank=item.get('rank')
                    )
                    scraped_products.append(product)
                except Exception as e:
                    logger.debug(f"Error converting product: {e}")
                    continue
            
            logger.info(f"Scraped {len(scraped_products)} products total")
            
            # Step 2: Analyze products and calculate trend scores
            logger.info("Step 2: Analyzing products and calculating trend scores...")
            trending_products = await self.trend_analyzer.analyze_products(scraped_products)
            
            if not trending_products:
                error_msg = "No products analyzed successfully"
                logger.error(error_msg)
                await self.discord_notifier.send_error_notification(error_msg)
                return
            
            # Step 3: Get top 10 and hot products
            top_10 = trending_products[:10]
            hot_products = self.trend_analyzer.get_hot_products(trending_products, threshold=70.0)
            
            logger.info(f"Top 10 products selected, {len(hot_products)} hot products (score ≥70)")
            
            # Step 4: Store in database
            logger.info("Step 3: Storing results in Supabase...")
            stored_count = 0
            
            for product in top_10:
                # Check if product already exists
                existing = db.get_product_by_name(product.product_name)
                
                if existing:
                    # Update existing product
                    product_id = existing['id']
                    updated = db.update_trending_product(product_id, product)
                    
                    if updated:
                        stored_count += 1
                        # Record history
                        history = TrendHistory(
                            product_id=product_id,
                            trend_score=product.trend_score,
                            search_volume=product.search_volume
                        )
                        db.insert_trend_history(history)
                else:
                    # Insert new product
                    inserted = db.insert_trending_product(product)
                    
                    if inserted:
                        stored_count += 1
                        # Record initial history
                        history = TrendHistory(
                            product_id=inserted['id'],
                            trend_score=product.trend_score,
                            search_volume=product.search_volume
                        )
                        db.insert_trend_history(history)
            
            logger.info(f"Stored/updated {stored_count} products in database")
            
            # Step 5: Archive old products
            db.archive_old_products(days=30)
            
            # Step 6: Send Discord notification
            logger.info("Step 4: Sending Discord notification...")
            await self.discord_notifier.send_trend_summary(
                products=top_10,
                hot_count=len(hot_products)
            )
            
            # Job complete
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            logger.info("="*60)
            logger.info(f"Trend detection job completed in {duration:.1f} seconds")
            logger.info(f"Results: {len(top_10)} products stored, {len(hot_products)} hot products")
            logger.info("="*60)
        
        except Exception as e:
            logger.error(f"Fatal error in trend detection job: {e}", exc_info=True)
            await self.discord_notifier.send_error_notification(str(e))
    
    def start(self):
        """Start the scheduler"""
        # Schedule daily job at specified time (UTC)
        self.scheduler.add_job(
            self.run_trend_detection,
            trigger=CronTrigger(
                hour=settings.cron_hour,
                minute=settings.cron_minute,
                timezone='UTC'
            ),
            id='daily_trend_detection',
            name='Daily Trend Detection Job',
            replace_existing=True
        )
        
        # Also run immediately on startup (for testing)
        self.scheduler.add_job(
            self.run_trend_detection,
            'date',
            run_date=datetime.now(),
            id='startup_job',
            name='Startup Job'
        )
        
        self.scheduler.start()
        logger.info(f"Scheduler started. Daily job scheduled for {settings.cron_hour:02d}:{settings.cron_minute:02d} UTC")
    
    def shutdown(self):
        """Shutdown the scheduler"""
        self.scheduler.shutdown()
        logger.info("Scheduler shut down")


# Global scheduler instance
scheduler = TrendDetectionScheduler()
