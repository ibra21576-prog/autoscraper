import re
import logging
from urllib.parse import urlencode
from bs4 import BeautifulSoup
from .base import BaseScraper

logger = logging.getLogger(__name__)

BRAND_SLUGS = {
    'audi': 'audi', 'bmw': 'bmw', 'mercedes-benz': 'mercedes-benz', 'volkswagen': 'volkswagen',
    'opel': 'opel', 'ford': 'ford', 'porsche': 'porsche', 'toyota': 'toyota',
    'honda': 'honda', 'hyundai': 'hyundai', 'kia': 'kia', 'mazda': 'mazda',
    'nissan': 'nissan', 'peugeot': 'peugeot', 'renault': 'renault', 'seat': 'seat',
    'skoda': 'skoda', 'volvo': 'volvo', 'fiat': 'fiat', 'citroen': 'citroen',
    'mini': 'mini', 'tesla': 'tesla', 'smart': 'smart', 'mitsubishi': 'mitsubishi',
    'suzuki': 'suzuki', 'dacia': 'dacia', 'land rover': 'land-rover', 'jaguar': 'jaguar',
    'alfa romeo': 'alfa-romeo', 'chevrolet': 'chevrolet', 'jeep': 'jeep', 'subaru': 'subaru',
    'lexus': 'lexus', 'cupra': 'cupra',
}


class AutoScout24Scraper(BaseScraper):
    """Scraper für AutoScout24 Fahrzeugangebote."""

    BASE_URL = 'https://www.autoscout24.de/lst'
    PLATFORM = 'autoscout24'

    def search(self, brand=None, model=None, price_min=None, price_max=None,
               year_min=None, mileage_max=None, fuel_type=None, page=1):
        """Suche auf AutoScout24 durchführen."""
        # URL-Pfad aufbauen
        path_parts = []
        if brand:
            brand_slug = BRAND_SLUGS.get(brand.lower(), brand.lower())
            path_parts.append(brand_slug)

        path = '/'.join(path_parts) if path_parts else '-'

        params = {
            'sort': 'age',
            'desc': '1',
            'cy': 'D',
            'atype': 'C',
            'page': page,
        }

        if price_min:
            params['pricefrom'] = price_min
        if price_max:
            params['priceto'] = price_max
        if year_min:
            params['fregfrom'] = year_min
        if mileage_max:
            params['kmto'] = mileage_max
        if fuel_type:
            fuel_map = {
                'benzin': 'B', 'diesel': 'D', 'elektro': 'E',
                'hybrid': 'M', 'gas': 'L',
            }
            if fuel_type.lower() in fuel_map:
                params['fuel'] = fuel_map[fuel_type.lower()]

        url = f'{self.BASE_URL}/{path}?{urlencode(params)}'
        logger.info(f"AutoScout24 search: {url}")

        response = self._request(url)
        if not response:
            return []

        return self._parse_results(response.text)

    def _parse_results(self, html):
        """Suchergebnisse aus HTML parsen."""
        soup = BeautifulSoup(html, 'html5lib')
        results = []

        # AutoScout24 Listing-Container
        listings = soup.select('[data-testid="listing"]')
        if not listings:
            listings = soup.select('article[class*="cldt-summary-full-item"]')
        if not listings:
            listings = soup.select('.cl-list-element')

        for listing in listings:
            try:
                car = self._parse_single(listing)
                if car and car.get('title'):
                    results.append(car)
            except Exception as e:
                logger.debug(f"Failed to parse listing: {e}")
                continue

        logger.info(f"AutoScout24: {len(results)} Ergebnisse gefunden")
        return results

    def _parse_single(self, listing):
        """Einzelnes Listing parsen."""
        car = {'platform': self.PLATFORM}

        # Link & ID
        link = listing.find('a', href=re.compile(r'/angebote/|/offers/'))
        if not link:
            link = listing.find('a', href=True)
        if link:
            href = link.get('href', '')
            if not href.startswith('http'):
                href = 'https://www.autoscout24.de' + href
            car['url'] = href
            id_match = re.search(r'/(\d+)\??|id[=-](\d+)', href)
            if id_match:
                car['external_id'] = id_match.group(1) or id_match.group(2)

        if 'external_id' not in car:
            car['external_id'] = str(hash(str(listing)[:200]))

        # Titel
        title_el = listing.find(['h2', 'h3', 'a'], class_=re.compile(r'title|heading|name', re.I))
        if not title_el and link:
            title_el = link
        car['title'] = title_el.get_text(strip=True) if title_el else ''

        # Marke & Modell
        car['brand'], car['model'] = self._extract_brand_model(car['title'])

        # Preis
        price_el = listing.find(string=re.compile(r'[\d.]+\s*€|EUR'))
        if not price_el:
            price_el = listing.find(class_=re.compile(r'price', re.I))
        if price_el:
            price_text = price_el.get_text(strip=True) if hasattr(price_el, 'get_text') else str(price_el)
            car['price'] = self._parse_price(price_text)

        # Bild
        img = listing.find('img', src=re.compile(r'https?://'))
        if not img:
            img = listing.find('img', attrs={'data-src': re.compile(r'https?://')})
        if img:
            car['image_url'] = img.get('src') or img.get('data-src', '')

        # Details
        details_text = listing.get_text(' ', strip=True)

        km_match = re.search(r'([\d.]+)\s*km', details_text, re.I)
        if km_match:
            car['mileage'] = self._parse_mileage(km_match.group(1))

        year_match = re.search(r'(\d{2})/(\d{4})', details_text)
        if year_match:
            car['year'] = int(year_match.group(2))

        fuel_patterns = {
            'Benzin': 'Benzin', 'Diesel': 'Diesel', 'Elektro': 'Elektro',
            'Hybrid': 'Hybrid', 'Erdgas': 'Gas',
        }
        for pattern, fuel in fuel_patterns.items():
            if pattern.lower() in details_text.lower():
                car['fuel_type'] = fuel
                break

        ps_match = re.search(r'(\d+)\s*PS|(\d+)\s*kW', details_text)
        if ps_match:
            car['power'] = ps_match.group(0)

        loc_el = listing.find(class_=re.compile(r'location|city|seller', re.I))
        if loc_el:
            car['location'] = loc_el.get_text(strip=True)

        return car

    def _extract_brand_model(self, title):
        """Marke und Modell aus dem Titel extrahieren."""
        if not title:
            return '', ''
        title_lower = title.lower()
        for brand_name in sorted(BRAND_SLUGS.keys(), key=len, reverse=True):
            if brand_name in title_lower:
                idx = title_lower.index(brand_name)
                model = title[idx + len(brand_name):].strip(' -,')
                model = model.split(',')[0].strip() if ',' in model else model.split(' ')[0].strip()
                return brand_name.title(), model
        parts = title.split(' ', 1)
        return parts[0] if parts else '', parts[1].split(',')[0].strip() if len(parts) > 1 else ''
