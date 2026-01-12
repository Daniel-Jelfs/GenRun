"""
Amazon Best Sellers Scraper - Updated with multiple selector strategies
"""
import time
import random
import logging
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import requests
from fake_useragent import UserAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AmazonScraper:
    """Scrape Amazon Best Sellers using requests + BeautifulSoup"""
    
    def __init__(self, request_delay: int = 3, max_retries: int = 3):
        self.request_delay = request_delay
        self.max_retries = max_retries
        self.ua = UserAgent()
        self.session = requests.Session()
        
        # Updated categories with correct URLs
        self.categories = {
            "Home": "https://www.amazon.com/Best-Sellers/zgbs/",
            "Electronics": "https://www.amazon.com/Best-Sellers-Electronics/zgbs/electronics/",
            "Fashion": "https://www.amazon.com/Best-Sellers-Fashion/zgbs/fashion/",
            "Beauty": "https://www.amazon.com/Best-Sellers-Beauty/zgbs/beauty/",
            "Sports": "https://www.amazon.com/Best-Sellers-Sports-Outdoors/zgbs/sporting-goods/"
        }
    
    def _get_headers(self) -> Dict[str, str]:
        """Generate realistic headers"""
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.amazon.com/'
        }
    
    def _fetch_page(self, url: str, category: str) -> Optional[str]:
        """Fetch page with retries and exponential backoff"""
        for attempt in range(self.max_retries):
            try:
                delay = self.request_delay + random.uniform(1, 3)
                time.sleep(delay)
                
                response = self.session.get(
                    url,
                    headers=self._get_headers(),
                    timeout=30,
                    allow_redirects=True
                )
                
                if response.status_code == 200:
                    logger.info(f"Successfully fetched {category}")
                    return response.text
                elif response.status_code == 429:
                    wait_time = 10 * (attempt + 1)
                    logger.warning(f"Rate limited on {category}, waiting {wait_time}s")
                    time.sleep(wait_time)
                elif response.status_code == 503:
                    wait_time = 15 * (attempt + 1)
                    logger.warning(f"Service unavailable for {category}, waiting {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logger.warning(f"HTTP {response.status_code} for {category}")
                    
            except Exception as e:
                logger.error(f"Error fetching {category}: {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(5 * (attempt + 1))
        
        logger.error(f"Failed to fetch {category} after {self.max_retries} attempts")
        return None
    
    def _extract_product_info(self, element, category: str) -> Optional[Dict]:
        """Extract product information using multiple strategies"""
        try:
            # Strategy 1: Try multiple title selectors
            title = None
            title_selectors = [
                {'class_': 'p13n-sc-truncate'},
                {'class_': '_cDEzb_p13n-sc-css-line-clamp-3_g3dy1'},
                {'class_': 'a-link-normal'},
                {'id': lambda x: x and 'title' in x.lower()}
            ]
            
            for selector in title_selectors:
                title_elem = element.find(['div', 'span', 'a'], selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    if title and len(title) > 3:
                        break
            
            if not title:
                return None
            
            # Strategy 2: Try multiple URL patterns
            url = None
            url_elem = element.find('a', href=True)
            if url_elem:
                href = url_elem['href']
                if href.startswith('http'):
                    url = href
                elif href.startswith('/'):
                    url = f"https://www.amazon.com{href}"
            
            if not url:
                return None
            
            # Strategy 3: Extract price (multiple patterns)
            price = 0.0
            price_selectors = [
                {'class_': 'a-price'},
                {'class_': 'p13n-sc-price'},
                {'class_': '_cDEzb_p13n-sc-price_3mJ9Z'}
            ]
            
            for selector in price_selectors:
                price_elem = element.find('span', selector)
                if price_elem:
                    offscreen = price_elem.find('span', {'class_': 'a-offscreen'})
                    if offscreen:
                        try:
                            price_text = offscreen.get_text(strip=True).replace('$', '').replace(',', '')
                            price = float(price_text)
                            break
                        except (ValueError, AttributeError):
                            pass
            
            # Strategy 4: Extract rating
            rating = None
            rating_elem = element.find('span', {'class_': 'a-icon-alt'})
            if rating_elem:
                try:
                    rating_text = rating_elem.get_text(strip=True)
                    rating = float(rating_text.split()[0])
                except (ValueError, IndexError):
                    pass
            
            # Strategy 5: Extract review count
            review_count = 0
            review_elem = element.find('span', {'class_': 'a-size-small'})
            if review_elem:
                try:
                    review_text = review_elem.get_text(strip=True).replace(',', '')
                    review_count = int(''.join(filter(str.isdigit, review_text)))
                except ValueError:
                    pass
            
            return {
                'name': title,
                'url': url,
                'price': price,
                'category': category,
                'rating': rating,
                'review_count': review_count
            }
            
        except Exception as e:
            logger.debug(f"Error extracting product: {str(e)}")
            return None
    
    def scrape_category(self, category: str, url: str, max_products: int = 50) -> List[Dict]:
        """Scrape products from a category using multiple selector strategies"""
        logger.info(f"Scraping Amazon {category} category...")
        
        html = self._fetch_page(url, category)
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'lxml')
        products = []
        
        # Try multiple container selectors
        container_strategies = [
            # Strategy 1: ID-based grid items
            {'id': lambda x: x and x.startswith('gridItemRoot')},
            # Strategy 2: Common class patterns
            {'class_': 'zg-grid-general-faceout'},
            {'class_': 'p13n-sc-uncoverable-faceout'},
            {'class_': 'a-carousel-card'},
            # Strategy 3: Data attributes
            {'attrs': {'data-asin': True}},
            # Strategy 4: Generic containers with links
            {'class_': lambda x: x and 'item' in str(x).lower()}
        ]
        
        product_elements = []
        for strategy in container_strategies:
            elements = soup.find_all('div', strategy)
            if elements:
                logger.info(f"Found {len(elements)} elements using strategy: {strategy}")
                product_elements = elements
                break
        
        if not product_elements:
            logger.warning(f"No product containers found in {category}")
            return []
        
        logger.info(f"Found {len(product_elements)} product elements in {category}")
        
        # Extract products
        for element in product_elements[:max_products]:
            product = self._extract_product_info(element, category)
            if product:
                products.append(product)
                logger.info(f"Extracted: {product['name'][:40]}... (${product['price']})")
        
        logger.info(f"Scraped {len(products)} products from {category}")
        return products
    
    def scrape_all_categories(self, products_per_category: int = 50) -> List[Dict]:
        """Scrape all categories"""
        logger.info(f"Starting Amazon scrape - {len(self.categories)} categories")
        all_products = []
        
        for i, (category, url) in enumerate(self.categories.items(), 1):
            try:
                logger.info(f"Category {i}/{len(self.categories)}: {category}")
                products = self.scrape_category(category, url, products_per_category)
                all_products.extend(products)
                
                # Longer delay between categories
                if i < len(self.categories):
                    delay = self.request_delay + random.uniform(3, 8)
                    logger.info(f"Waiting {delay:.1f}s before next category...")
                    time.sleep(delay)
                
            except Exception as e:
                logger.error(f"Error scraping {category}: {str(e)}")
                continue
        
        logger.info(f"Total products scraped from Amazon: {len(all_products)}")
        return all_products


if __name__ == "__main__":
    logger.info("Testing Amazon scraper...")
    scraper = AmazonScraper(request_delay=4, max_retries=3)
    
    # Test with 5 products per category
    products = scraper.scrape_all_categories(products_per_category=5)
    
    logger.info(f"\nResults: {len(products)} total products")
    
    if products:
        logger.info("\nSample products:")
        for product in products[:3]:
            print(f"\n{product['name']}")
            print(f"Category: {product['category']}")
            print(f"Price: ${product['price']:.2f}")
            print(f"URL: {product['url'][:60]}...")
    else:
        logger.warning("No products were scraped - Amazon may be blocking or selectors need updating")
