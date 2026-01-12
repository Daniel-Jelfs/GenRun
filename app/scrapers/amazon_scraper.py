import asyncio
import logging
from typing import List, Optional
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
from app.models import ScrapedProduct
from app.config import settings
import re
import os

logger = logging.getLogger(__name__)


class AmazonScraper:
    """Scraper for Amazon Best Sellers"""
    
    CATEGORIES = {
        "Home": "https://www.amazon.com/Best-Sellers-Home-Kitchen/zgbs/home-garden",
        "Electronics": "https://www.amazon.com/Best-Sellers-Electronics/zgbs/electronics",
        "Fashion": "https://www.amazon.com/Best-Sellers-Fashion/zgbs/fashion",
        "Beauty": "https://www.amazon.com/Best-Sellers-Beauty/zgbs/beauty",
        "Sports": "https://www.amazon.com/Best-Sellers-Sports-Outdoors/zgbs/sporting-goods"
    }
    
    def __init__(self):
        self.products: List[ScrapedProduct] = []
    
    async def scrape_category(self, category: str, url: str, max_products: int = 50) -> List[ScrapedProduct]:
        """Scrape a single category"""
        products = []
        
        try:
            async with async_playwright() as p:
                # Let Playwright find the browser automatically
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu'
                    ]
                )
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                )
                page = await context.new_page()
                
                logger.info(f"Scraping Amazon {category} category...")
                
                try:
                    await page.goto(url, timeout=settings.timeout * 1000, wait_until="networkidle")
                    await asyncio.sleep(2)  # Let page fully load
                    
                    content = await page.content()
                    soup = BeautifulSoup(content, 'lxml')
                    
                    # Find product cards
                    product_items = soup.select('.zg-grid-general-faceout')[:max_products]
                    
                    for idx, item in enumerate(product_items, 1):
                        try:
                            # Extract product name
                            name_elem = item.select_one('.p13n-sc-truncate-desktop-type2')
                            if not name_elem:
                                name_elem = item.select_one('._cDEzb_p13n-sc-css-line-clamp-3_g3dy1')
                            
                            name = name_elem.get_text(strip=True) if name_elem else None
                            
                            # Extract product URL
                            link_elem = item.select_one('a.a-link-normal')
                            product_url = 'https://www.amazon.com' + link_elem['href'] if link_elem else None
                            
                            # Extract price
                            price_elem = item.select_one('.p13n-sc-price, ._cDEzb_p13n-sc-price_3mJ9Z')
                            price_text = price_elem.get_text(strip=True) if price_elem else None
                            price = self._extract_price(price_text) if price_text else None
                            
                            if name and product_url:
                                product = ScrapedProduct(
                                    name=name,
                                    category=category,
                                    url=product_url,
                                    price=price,
                                    rank=idx
                                )
                                products.append(product)
                                logger.debug(f"Found product: {name[:50]}...")
                        
                        except Exception as e:
                            logger.warning(f"Error parsing product in {category}: {e}")
                            continue
                    
                    logger.info(f"Scraped {len(products)} products from {category}")
                
                except PlaywrightTimeout:
                    logger.error(f"Timeout loading {category} page")
                except Exception as e:
                    logger.error(f"Error scraping {category}: {e}")
                
                finally:
                    await browser.close()
                    await asyncio.sleep(settings.request_delay)
        
        except Exception as e:
            logger.error(f"Fatal error in Amazon scraper for {category}: {e}")
        
        return products
    
    def _extract_price(self, price_text: str) -> Optional[float]:
        """Extract numeric price from text"""
        try:
            # Remove currency symbols and extract number
            price_match = re.search(r'\$?(\d+\.?\d*)', price_text.replace(',', ''))
            if price_match:
                return float(price_match.group(1))
        except Exception as e:
            logger.debug(f"Error extracting price from '{price_text}': {e}")
        return None
    
    async def scrape_all_categories(self, max_per_category: int = 50) -> List[ScrapedProduct]:
        """Scrape all categories"""
        all_products = []
        
        for category, url in self.CATEGORIES.items():
            products = await self.scrape_category(category, url, max_per_category)
            all_products.extend(products)
            
            # Delay between categories to avoid rate limiting
            await asyncio.sleep(settings.request_delay)
        
        logger.info(f"Total products scraped from Amazon: {len(all_products)}")
        return all_products
