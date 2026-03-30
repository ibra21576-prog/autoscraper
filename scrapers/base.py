import time
import random
import logging
import requests
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)


class BaseScraper:
    """Basis-Klasse für alle Auto-Scraper."""

    def __init__(self):
        self.session = requests.Session()
        self.ua = UserAgent()
        self.delay_min = 2
        self.delay_max = 5

    def _get_headers(self):
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    def _request(self, url):
        """HTTP GET mit Rate-Limiting und Error-Handling."""
        time.sleep(random.uniform(self.delay_min, self.delay_max))
        try:
            response = self.session.get(url, headers=self._get_headers(), timeout=15)
            if response.status_code == 200:
                return response
            elif response.status_code == 429:
                logger.warning(f"Rate limited on {url}, waiting 30s...")
                time.sleep(30)
                return None
            elif response.status_code == 403:
                logger.warning(f"Access denied (403) for {url} - possible captcha/block")
                return None
            else:
                logger.error(f"HTTP {response.status_code} for {url}")
                return None
        except requests.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            return None

    def search(self, **kwargs):
        """Muss von Subklassen implementiert werden."""
        raise NotImplementedError

    def _parse_price(self, price_str):
        """Preis-String zu Integer konvertieren."""
        if not price_str:
            return None
        cleaned = price_str.replace('.', '').replace(',', '').replace('€', '').replace('EUR', '')
        cleaned = ''.join(c for c in cleaned if c.isdigit())
        return int(cleaned) if cleaned else None

    def _parse_mileage(self, mileage_str):
        """Kilometerstand-String zu Integer konvertieren."""
        if not mileage_str:
            return None
        cleaned = ''.join(c for c in mileage_str if c.isdigit())
        return int(cleaned) if cleaned else None
