import time
import random
import logging
import requests
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

# Canonical brand names — maps any known variant/alias → official name
BRAND_NORMALIZE = {
    'vw': 'Volkswagen', 'volkswagen': 'Volkswagen',
    'mercedes-benz': 'Mercedes-Benz', 'mercedes': 'Mercedes-Benz', 'mb': 'Mercedes-Benz',
    'bmw': 'BMW',
    'audi': 'Audi',
    'opel': 'Opel',
    'ford': 'Ford',
    'porsche': 'Porsche',
    'toyota': 'Toyota',
    'honda': 'Honda',
    'hyundai': 'Hyundai',
    'kia': 'Kia',
    'seat': 'Seat',
    'skoda': 'Skoda', 'škoda': 'Skoda',
    'renault': 'Renault',
    'peugeot': 'Peugeot',
    'fiat': 'Fiat',
    'volvo': 'Volvo',
    'mazda': 'Mazda',
    'nissan': 'Nissan',
    'citroen': 'Citroën', 'citroën': 'Citroën', 'citroen': 'Citroën',
    'mini': 'MINI',
    'tesla': 'Tesla',
    'smart': 'Smart',
    'suzuki': 'Suzuki',
    'mitsubishi': 'Mitsubishi',
    'dacia': 'Dacia',
    'land rover': 'Land Rover', 'land-rover': 'Land Rover',
    'jaguar': 'Jaguar',
    'jeep': 'Jeep',
    'subaru': 'Subaru',
    'lexus': 'Lexus',
    'cupra': 'Cupra',
    'alfa romeo': 'Alfa Romeo', 'alfa-romeo': 'Alfa Romeo', 'alfa': 'Alfa Romeo',
    'chevrolet': 'Chevrolet',
    'dodge': 'Dodge',
    'cadillac': 'Cadillac',
    'chrysler': 'Chrysler',
    'maserati': 'Maserati',
    'ferrari': 'Ferrari',
    'lamborghini': 'Lamborghini',
    'bentley': 'Bentley',
    'rolls-royce': 'Rolls-Royce', 'rolls royce': 'Rolls-Royce',
    'aston martin': 'Aston Martin',
    'mclaren': 'McLaren',
    'genesis': 'Genesis',
    'polestar': 'Polestar',
    'mg': 'MG',
    'byd': 'BYD',
    'nio': 'NIO',
    'xpeng': 'Xpeng',
    'ds automobiles': 'DS Automobiles', 'ds': 'DS Automobiles',
    'lancia': 'Lancia',
    'abarth': 'Abarth',
    'saab': 'Saab',
    'ssangyong': 'SsangYong', 'ssang yong': 'SsangYong',
    'infiniti': 'Infiniti',
    'alpine': 'Alpine',
    'rover': 'Rover',
    'lynk & co': 'Lynk & Co', 'lynk': 'Lynk & Co',
    'daihatsu': 'Daihatsu',
    'isuzu': 'Isuzu',
    'lada': 'Lada',
    'brabus': 'Brabus',
}

# All known brand strings to search for in titles (longest first to avoid partial matches)
_KNOWN_BRANDS = sorted(BRAND_NORMALIZE.keys(), key=len, reverse=True)


def normalize_brand(raw: str) -> str:
    """Return canonical brand name, or the input title-cased if unknown."""
    if not raw:
        return ''
    return BRAND_NORMALIZE.get(raw.strip().lower(), raw.strip().title())


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

    def _extract_brand_model(self, title):
        """Marke und Modell aus Titel extrahieren — mit vollständiger Normalisierung."""
        if not title:
            return '', ''
        title_lower = title.lower()
        for alias in _KNOWN_BRANDS:
            if alias in title_lower:
                canonical = normalize_brand(alias)
                idx = title_lower.index(alias)
                rest = title[idx + len(alias):].strip(' -,/')
                # Take first meaningful token as model
                model = rest.split(',')[0].strip().split(' ')[0].strip(' -,/') if rest else ''
                return canonical, model
        # Fallback: first word as brand, second as model
        parts = title.split(' ', 2)
        brand_raw = parts[0] if parts else ''
        model_raw = parts[1].split(',')[0].strip() if len(parts) > 1 else ''
        return normalize_brand(brand_raw), model_raw
