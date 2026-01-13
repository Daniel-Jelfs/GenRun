"""
Amazon Best Sellers Scraper - Multi-region support (US & UK)
"""
import time
import random
import logging
import re
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import requests
from fake_useragent import UserAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AmazonScraper:
    """Scrape Amazon Best Sellers using requests + BeautifulSoup"""
    
    # Region configurations - using zgbs URLs which work better
    REGIONS = {
        "US": {
            "base_url": "https://www.amazon.com",
            "currency": "$",
            "categories": {
                "Home": "/Best-Sellers-Home-Kitchen/zgbs/home-garden/ref=zg_bs_nav_home-garden_0",
                "Electronics": "/Best-Sellers-Electronics/zgbs/electronics/ref=zg_bs_nav_electronics_0",
                "Fashion": "/Best-Sellers-Clothing-Shoes-Jewelry/zgbs/fashion/ref=zg_bs_nav_fashion_0",
                "Beauty": "/Best-Sellers-Beauty-Personal-Care/zgbs/beauty/ref=zg_bs_nav_beauty_0",
                "Sports": "/Best-Sellers-Sports-Outdoors/zgbs/sporting-goods/ref=zg_bs_nav_sporting-goods_0"
            }
        },
        "UK": {
            "base_url": "https://www.amazon.co.uk",
            "currency": "£",
            "categories": {
                "Home": "/Best-Sellers-Kitchen-Home/zgbs/kitchen/ref=zg_bs_nav_kitchen_0",
                "Electronics": "/Best-Sellers-Electronics/zgbs/electronics/ref=zg_bs_nav_electronics_0",
                "Fashion": "/Best-Sellers-Clothing/zgbs/fashion/ref=zg_bs_nav_fashion_0",
                "Beauty": "/Best-Sellers-Beauty/zgbs/beauty/ref=zg_bs_nav_beauty_0",
                "Sports": "/Best-Sellers-Sports-Outdoors/zgbs/sports/ref=zg_bs_nav_sports_0"
            }
        }
    }
    
    def __init__(self, region: str = "US", request_delay: int = 3, max_retries: int = 3):
        self.region = region.upper()
        if self.region not in self.REGIONS:
            self.region = "US"
        
        self.request_delay = request_delay
        self.max_retries = max_retries
        self.ua = UserAgent()
        self.session = requests.Session()
        
        self.config = self.REGIONS[self.region]
        self.base_url = self.config["base_url"]
        self.currency = self.config["currency"]
        self.categories = self.config["categories"]
        
        logger.info(f"Amazon Scraper initialized for region: {self.region}")
    
    def _get_headers(self) -> Dict[str, str]:
        """Generate realistic headers"""
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-GB,en;q=0.9,en-US;q=0.8' if self.region == "UK" else 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
    
    def _fetch_page(self, url: str, category: str) -> Optional[str]:
        """Fetch page with retries and exponential backoff"""
        for attempt in range(self.max_retries):
            try:
                delay = self.request_delay + random.uniform(2, 5)
                time.sleep(delay)
                
                headers = self._get_headers()
                logger.info(f"Fetching {category} from {url}")
                
                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=30,
                    allow_redirects=True
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Successfully fetched {category} ({len(response.text)} bytes)")
                    return response.text
                elif response.status_code == 429:
                    wait_time = 15 * (attempt + 1) + random.uniform(5, 15)
                    logger.warning(f"⚠️ Rate limited on {category}, waiting {wait_time:.0f}s...")
                    time.sleep(wait_time)
                elif response.status_code == 503:
                    wait_time = 20 * (attempt + 1) + random.uniform(5, 15)
                    logger.warning(f"⚠️ Service unavailable for {category}, waiting {wait_time:.0f}s...")
                    time.sleep(wait_time)
                else:
                    logger.warning(f"⚠️ HTTP {response.status_code} for {category}")
                    
            except Exception as e:
                logger.error(f"❌ Error fetching {category}: {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(10 * (attempt + 1))
        
        logger.error(f"❌ Failed to fetch {category} after {self.max_retries} attempts")
        return None
    
    def _extract_products_from_html(self, html: str, category: str) -> List[Dict]:
        """Extract products using multiple selector strategies"""
        soup = BeautifulSoup(html, 'lxml')
        products = []
        
        # Multiple selector strategies
        selectors_to_try = [
            # Strategy 1: gridItemRoot (most common on bestseller pages)
            ('div', {'id': lambda x: x and x.startswith('gridItemRoot')}),
            # Strategy 2: zg-grid-general-faceout
            ('div', {'class': 'zg-grid-general-faceout'}),
            # Strategy 3: p13n-sc-uncoverable-faceout
            ('div', {'class': 'p13n-sc-uncoverable-faceout'}),
            # Strategy 4: data-asin attribute (product containers)
            ('div', {'data-asin': lambda x: x and len(x) == 10}),
            # Strategy 5: zg-item-immersion
            ('li', {'class': 'zg-item-immersion'}),
            # Strategy 6: Carousel cards
            ('div', {'class': 'a-carousel-card'}),
            # Strategy 7: Product grid items
            ('div', {'class': lambda x: x and 'zg-item' in ' '.join(x) if isinstance(x, list) else False}),
        ]
        
        product_elements = []
        used_strategy = None
        
        for tag, attrs in selectors_to_try:
            try:
                elements = soup.find_all(tag, attrs)
                if elements and len(elements) >= 3:
                    product_elements = elements
                    used_strategy = f"{tag} with {type(attrs).__name__}"
                    logger.info(f"📦 Found {len(elements)} elements using strategy: {tag}")
                    break
            except Exception as e:
                logger.debug(f"Selector failed: {e}")
                continue
        
        if not product_elements:
            # Fallback Strategy: Find all product links and extract info
            logger.info(f"🔍 Using fallback link extraction for {category}...")
            products = self._extract_from_links(soup, category)
            if products:
                logger.info(f"📦 Fallback found {len(products)} products")
                return products
            
            # Last resort: Try to find any divs with product-like structure
            logger.warning(f"⚠️ No products found for {category}, trying deep search...")
            products = self._deep_search_products(soup, category)
            return products
        
        # Process found elements
        for idx, element in enumerate(product_elements[:60], 1):
            try:
                product = self._extract_single_product(element, category, idx)
                if product:
                    products.append(product)
            except Exception as e:
                logger.debug(f"Error extracting product {idx}: {e}")
                continue
        
        return products
    
    def _extract_from_links(self, soup: BeautifulSoup, category: str) -> List[Dict]:
        """Extract products from links as fallback"""
        products = []
        seen_asins = set()
        
        # Find all links that look like product links
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            try:
                href = link.get('href', '')
                
                # Look for product links (contain /dp/ or /gp/product/)
                asin = None
                if '/dp/' in href:
                    match = re.search(r'/dp/([A-Z0-9]{10})', href)
                    if match:
                        asin = match.group(1)
                elif '/gp/product/' in href:
                    match = re.search(r'/gp/product/([A-Z0-9]{10})', href)
                    if match:
                        asin = match.group(1)
                
                if not asin or asin in seen_asins:
                    continue
                
                seen_asins.add(asin)
                
                # Get title - try multiple methods
                title = None
                
                # Method 1: title attribute
                title = link.get('title', '')
                
                # Method 2: Text content
                if not title or len(title) < 5:
                    title = link.get_text(strip=True)
                
                # Method 3: Child elements
                if not title or len(title) < 5:
                    for child in link.find_all(['span', 'div']):
                        text = child.get_text(strip=True)
                        if text and len(text) > 10 and len(text) < 200:
                            title = text
                            break
                
                # Method 4: Parent's title
                if not title or len(title) < 5:
                    parent = link.find_parent(['div', 'li'])
                    if parent:
                        title_elem = parent.find(['span', 'div'], class_=lambda x: x and 'truncate' in str(x).lower())
                        if title_elem:
                            title = title_elem.get_text(strip=True)
                
                if not title or len(title) < 5:
                    continue
                
                # Clean title
                title = re.sub(r'\s+', ' ', title).strip()
                if len(title) > 200:
                    title = title[:200]
                
                # Build URL
                if href.startswith('http'):
                    url = href
                else:
                    url = self.base_url + href
                url = url.split('?')[0]
                
                # Try to get price from nearby elements
                price = 0.0
                parent = link.find_parent(['div', 'li'])
                if parent:
                    price_elem = parent.find(['span'], class_=lambda x: x and 'price' in str(x).lower())
                    if price_elem:
                        price = self._parse_price(price_elem.get_text(strip=True))
                
                products.append({
                    'name': title,
                    'url': url,
                    'price': price,
                    'category': category,
                    'rank': len(products) + 1
                })
                
                if len(products) >= 50:
                    break
                    
            except Exception as e:
                continue
        
        return products
    
    def _deep_search_products(self, soup: BeautifulSoup, category: str) -> List[Dict]:
        """Deep search for any product-like content"""
        products = []
        seen_asins = set()
        
        # Find all elements that might contain product info
        # Look for any element with an ASIN
        for elem in soup.find_all(['div', 'li', 'article'], attrs={'data-asin': True}):
            try:
                asin = elem.get('data-asin', '')
                if not asin or len(asin) != 10 or asin in seen_asins:
                    continue
                
                seen_asins.add(asin)
                
                # Find title
                title = None
                for title_elem in elem.find_all(['a', 'span', 'h2', 'div']):
                    text = title_elem.get_text(strip=True)
                    if text and 10 < len(text) < 200:
                        title = text
                        break
                
                if not title:
                    continue
                
                # Find URL
                url = f"{self.base_url}/dp/{asin}"
                link = elem.find('a', href=True)
                if link:
                    href = link.get('href', '')
                    if href.startswith('http'):
                        url = href.split('?')[0]
                    elif href.startswith('/'):
                        url = self.base_url + href.split('?')[0]
                
                # Find price
                price = 0.0
                price_elem = elem.find(['span'], class_=lambda x: x and 'price' in str(x).lower())
                if price_elem:
                    price = self._parse_price(price_elem.get_text(strip=True))
                
                products.append({
                    'name': title[:200],
                    'url': url,
                    'price': price,
                    'category': category,
                    'rank': len(products) + 1
                })
                
                if len(products) >= 50:
                    break
                    
            except Exception:
                continue
        
        return products
    
    def _extract_single_product(self, element, category: str, rank: int) -> Optional[Dict]:
        """Extract product info from a single element"""
        
        # Find product title - try multiple approaches
        title = None
        title_selectors = [
            ('div', {'class': 'p13n-sc-truncate'}),
            ('div', {'class': '_cDEzb_p13n-sc-css-line-clamp-3_g3dy1'}),
            ('div', {'class': '_cDEzb_p13n-sc-css-line-clamp-4_2q2cc'}),
            ('span', {'class': 'zg-text-center-align'}),
            ('a', {'class': 'a-link-normal', 'tabindex': '-1'}),
            ('a', {'class': 'a-link-normal'}),
            ('span', {'class': 'a-size-small'}),
            ('span', {'class': 'a-size-base'}),
        ]
        
        for tag, attrs in title_selectors:
            title_elem = element.find(tag, attrs)
            if title_elem:
                # Get title from attribute or text
                title = title_elem.get('title', '') or title_elem.get_text(strip=True)
                if title and len(title) > 5:
                    break
        
        if not title:
            # Last resort: get any text from anchor
            anchor = element.find('a', href=True)
            if anchor:
                title = anchor.get('title') or anchor.get_text(strip=True)
        
        if not title or len(title) < 5:
            return None
        
        # Clean title
        title = re.sub(r'\s+', ' ', title).strip()[:200]
        
        # Find URL
        url = None
        link = element.find('a', href=True)
        if link:
            href = link.get('href', '')
            if href.startswith('http'):
                url = href
            elif href.startswith('/'):
                url = self.base_url + href
        
        if not url:
            return None
        
        # Clean URL
        url = url.split('?')[0]
        
        # Find price
        price = 0.0
        price_selectors = [
            ('span', {'class': 'a-price'}),
            ('span', {'class': 'p13n-sc-price'}),
            ('span', {'class': '_cDEzb_p13n-sc-price_3mJ9Z'}),
            ('span', {'class': 'a-color-price'}),
            ('span', {'class': 'a-offscreen'}),
        ]
        
        for tag, attrs in price_selectors:
            price_elem = element.find(tag, attrs)
            if price_elem:
                # Look for offscreen price (actual value)
                offscreen = price_elem.find('span', {'class': 'a-offscreen'})
                if offscreen:
                    price = self._parse_price(offscreen.get_text(strip=True))
                else:
                    price = self._parse_price(price_elem.get_text(strip=True))
                
                if price > 0:
                    break
        
        return {
            'name': title,
            'url': url,
            'price': price,
            'category': category,
            'rank': rank
        }
    
    def _parse_price(self, price_text: str) -> float:
        """Parse price from text"""
        try:
            # Remove currency symbols and clean
            cleaned = price_text.replace('$', '').replace('£', '').replace('€', '')
            cleaned = cleaned.replace(',', '').replace(' ', '')
            
            # Handle ranges like "29.99 - 39.99"
            if '-' in cleaned:
                cleaned = cleaned.split('-')[0]
            
            # Extract first number
            match = re.search(r'(\d+\.?\d*)', cleaned)
            if match:
                return float(match.group(1))
        except Exception:
            pass
        return 0.0
    
    def scrape_category(self, category: str, path: str, max_products: int = 50) -> List[Dict]:
        """Scrape products from a single category"""
        url = self.base_url + path
        logger.info(f"🔍 Scraping {self.region} Amazon - {category}...")
        
        html = self._fetch_page(url, category)
        if not html:
            return []
        
        products = self._extract_products_from_html(html, category)
        
        logger.info(f"✅ Scraped {len(products)} products from {category}")
        return products[:max_products]
    
    def scrape_all_categories(self, products_per_category: int = 50) -> List[Dict]:
        """Scrape all categories"""
        logger.info(f"🚀 Starting Amazon {self.region} scrape - {len(self.categories)} categories")
        all_products = []
        
        for i, (category, path) in enumerate(self.categories.items(), 1):
            try:
                logger.info(f"📦 Category {i}/{len(self.categories)}: {category}")
                products = self.scrape_category(category, path, products_per_category)
                all_products.extend(products)
                
                # Longer delay between categories
                if i < len(self.categories):
                    delay = self.request_delay + random.uniform(5, 12)
                    logger.info(f"⏳ Waiting {delay:.1f}s before next category...")
                    time.sleep(delay)
                
            except Exception as e:
                logger.error(f"❌ Error scraping {category}: {str(e)}")
                continue
        
        logger.info(f"🎉 Total products scraped from Amazon {self.region}: {len(all_products)}")
        return all_products
    
    def get_available_regions(self) -> List[str]:
        """Return list of available regions"""
        return list(self.REGIONS.keys())
    
    def set_region(self, region: str):
        """Change the scraper region"""
        region = region.upper()
        if region in self.REGIONS:
            self.region = region
            self.config = self.REGIONS[self.region]
            self.base_url = self.config["base_url"]
            self.currency = self.config["currency"]
            self.categories = self.config["categories"]
            logger.info(f"Region changed to: {self.region}")
        else:
            logger.warning(f"Invalid region: {region}. Available: {list(self.REGIONS.keys())}")


if __name__ == "__main__":
    # Test both regions
    for region in ["US", "UK"]:
        logger.info(f"\n{'='*50}")
        logger.info(f"Testing {region} scraper...")
        logger.info(f"{'='*50}\n")
        
        scraper = AmazonScraper(region=region, request_delay=4, max_retries=2)
        products = scraper.scrape_all_categories(products_per_category=5)
        
        logger.info(f"\n{region} Results: {len(products)} total products")
        
        if products:
            for product in products[:3]:
                print(f"\n{product['name'][:50]}...")
                print(f"  Category: {product['category']}")
                print(f"  Price: {scraper.currency}{product['price']:.2f}")
