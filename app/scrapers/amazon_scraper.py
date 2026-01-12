import logging
import time
import random
import re
from typing import List, Optional
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from app.models import ScrapedProduct
from app.config import settings

logger = logging.getLogger(__name__)


class AmazonScraper:
    """Scraper for Amazon Best Sellers using requests + BeautifulSoup"""
    
    CATEGORIES = {
        "Home": "https://www.amazon.com/Best-Sellers-Home-Kitchen/zgbs/home-garden",
        "Electronics": "https://www.amazon.com/Best-Sellers-Electronics/zgbs/electronics",
        "Fashion": "https://www.amazon.com/Best-Sellers-Fashion/zgbs/fashion",
        "Beauty": "https://www.amazon.com/Best-Sellers-Beauty/zgbs/beauty",
        "Sports": "https://www.amazon.com/Best-Sellers-Sports-Outdoors/zgbs/sporting-goods"
    }
    
    def __init__(self):
        self.products: List[ScrapedProduct] = []
        try:
            self.ua = UserAgent()
        except:
            self.ua = None
    
    def _get_headers(self) -> dict:
        """Get randomized headers to avoid detection"""
        user_agent = self.ua.random if self.ua else 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        
        return {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    def _extract_price(self, price_text: str) -> Optional[float]:
        """Extract numeric price from text"""
        if not price_text:
            return None
        try:
            price_match = re.search(r'\$?(\d+\.?\d*)', price_text.replace(',', ''))
            if price_match:
                return float(price_match.group(1))
        except Exception as e:
            logger.debug(f"Error extracting price from '{price_text}': {e}")
        return None
    
    def scrape_category(self, category: str, url: str, max_products: int = 50) -> List[ScrapedProduct]:
        """Scrape a single category using requests"""
        products = []
        
        try:
            logger.info(f"🔍 Scraping Amazon {category} category...")
            
            # Make request with headers
            response = requests.get(
                url, 
                headers=self._get_headers(),
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch {category}: HTTP {response.status_code}")
                return products
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Try multiple selectors (Amazon changes these frequently)
            product_items = []
            
            # Selector 1: Grid items
            product_items = soup.select('div[id^="gridItemRoot"]')[:max_products]
            
            # Selector 2: Alternative grid format
            if not product_items:
                product_items = soup.select('.zg-grid-general-faceout')[:max_products]
            
            # Selector 3: Another common format
            if not product_items:
                product_items = soup.select('.a-section.a-spacing-small')[:max_products]
            
            logger.info(f"Found {len(product_items)} product elements in {category}")
            
            for idx, item in enumerate(product_items, 1):
                try:
                    # Extract product name (try multiple selectors)
                    name = None
                    name_selectors = [
                        '.p13n-sc-truncate-desktop-type2',
                        '._cDEzb_p13n-sc-css-line-clamp-3_g3dy1',
                        '.zg-text-center-align',
                        '.a-link-normal span',
                        'a[href*="/dp/"] span'
                    ]
                    
                    for selector in name_selectors:
                        name_elem = item.select_one(selector)
                        if name_elem:
                            name = name_elem.get_text(strip=True)
                            if name and len(name) > 5:
                                break
                    
                    # Extract product URL
                    product_url = None
                    link_elem = item.select_one('a.a-link-normal[href*="/dp/"]')
                    if not link_elem:
                        link_elem = item.select_one('a[href*="/dp/"]')
                    if link_elem and link_elem.get('href'):
                        href = link_elem['href']
                        if href.startswith('/'):
                            product_url = 'https://www.amazon.com' + href
                        else:
                            product_url = href
                    
                    # Extract price
                    price = None
                    price_selectors = [
                        '.p13n-sc-price',
                        '._cDEzb_p13n-sc-price_3mJ9Z',
                        '.a-price .a-offscreen',
                        '.a-color-price'
                    ]
                    
                    for selector in price_selectors:
                        price_elem = item.select_one(selector)
                        if price_elem:
                            price_text = price_elem.get_text(strip=True)
                            price = self._extract_price(price_text)
                            if price:
                                break
                    
                    # Only add if we have at least a name
                    if name and len(name) > 5:
                        product = ScrapedProduct(
                            name=name[:200],  # Truncate long names
                            category=category,
                            url=product_url or url,
                            price=price,
                            rank=idx
                        )
                        products.append(product)
                        logger.debug(f"  ✅ Product {idx}: {name[:50]}...")
                
                except Exception as e:
                    logger.warning(f"Error parsing product {idx} in {category}: {e}")
                    continue
            
            logger.info(f"✅ Scraped {len(products)} products from {category}")
        
        except requests.exceptions.Timeout:
            logger.error(f"⏰ Timeout scraping {category}")
        except requests.exceptions.RequestException as e:
            logger.error(f"🌐 Network error scraping {category}: {e}")
        except Exception as e:
            logger.error(f"❌ Fatal error in Amazon scraper for {category}: {e}")
        
        return products
    
    async def scrape_all_categories(self, max_per_category: int = 50) -> List[ScrapedProduct]:
        """Scrape all categories"""
        all_products = []
        
        logger.info(f"🚀 Starting Amazon scrape - {len(self.CATEGORIES)} categories")
        
        for i, (category, url) in enumerate(self.CATEGORIES.items(), 1):
            logger.info(f"📦 Category {i}/{len(self.CATEGORIES)}: {category}")
            
            products = self.scrape_category(category, url, max_per_category)
            all_products.extend(products)
            
            # Random delay between categories (2-5 seconds)
            delay = random.uniform(2, 5)
            logger.debug(f"⏳ Waiting {delay:.1f}s before next category...")
            time.sleep(delay)
        
        logger.info(f"🎉 Total products scraped from Amazon: {len(all_products)}")
        return all_products


# For testing
if __name__ == "__main__":
    import asyncio
    
    logging.basicConfig(level=logging.INFO)
    print("🧪 Testing Amazon scraper...")
    
    scraper = AmazonScraper()
    
    # Test single category
    products = scraper.scrape_category("Electronics", scraper.CATEGORIES["Electronics"], max_products=10)
    
    print(f"\n📊 Results:")
    print(f"  Products found: {len(products)}")
    
    for i, p in enumerate(products[:5], 1):
        print(f"  {i}. {p.name[:50]}... - ${p.price or 'N/A'}")
    
    print("\n✅ Test complete!")
