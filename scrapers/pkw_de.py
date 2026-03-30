import re
import logging
from urllib.parse import urlencode, quote
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
    'alfa romeo': 'alfa-romeo', 'chevrolet': 'chevrolet', 'jeep': 'jeep',
    'subaru': 'subaru', 'lexus': 'lexus', 'cupra': 'cupra',
}


class PkwDeScraper(BaseScraper):
    """Scraper für pkw.de Fahrzeugangebote."""

    BASE_URL = 'https://www.pkw.de'
    PLATFORM = 'pkw_de'

    def search(self, brand=None, model=None, price_min=None, price_max=None,
               year_min=None, mileage_max=None, fuel_type=None, page=1):
        """Suche auf pkw.de durchführen."""
        params = {
            'sortby': 'createdate_desc',
        }

        path = '/gebrauchtwagen'
        if brand:
            slug = BRAND_SLUGS.get(brand.lower(), brand.lower().replace(' ', '-'))
            path += f'/{slug}'
            if model:
                model_slug = model.lower().replace(' ', '-')
                path += f'/{model_slug}'

        if price_min:
            params['pricefrom'] = price_min
        if price_max:
            params['priceto'] = price_max
        if year_min:
            params['yearto'] = 2026
            params['yearfrom'] = year_min
        if mileage_max:
            params['mileageto'] = mileage_max
        if fuel_type:
            fuel_map = {'benzin': 'petrol', 'diesel': 'diesel', 'elektro': 'electric', 'hybrid': 'hybrid'}
            if fuel_type.lower() in fuel_map:
                params['fuel'] = fuel_map[fuel_type.lower()]
        if page > 1:
            params['pg'] = page

        url = f'{self.BASE_URL}{path}?{urlencode(params)}'
        logger.info(f"pkw.de search: {url}")

        response = self._request(url)
        if not response:
            return []

        return self._parse_results(response.text)

    def _parse_results(self, html):
        soup = BeautifulSoup(html, 'html5lib')
        results = []

        listings = soup.select('[data-listing-id]')
        if not listings:
            listings = soup.select('.listing-item')
        if not listings:
            listings = soup.select('article')
            listings = [l for l in listings if l.find('a', href=re.compile(r'/auto/'))]

        for listing in listings:
            try:
                car = self._parse_single(listing)
                if car and car.get('title'):
                    results.append(car)
            except Exception as e:
                logger.debug(f"pkw.de parse error: {e}")

        logger.info(f"pkw.de: {len(results)} Ergebnisse")
        return results

    def _parse_single(self, listing):
        car = {'platform': self.PLATFORM}

        listing_id = listing.get('data-listing-id', '')
        if listing_id:
            car['external_id'] = str(listing_id)
        else:
            link = listing.find('a', href=re.compile(r'/auto/|/gebrauchtwagen/'))
            if link:
                href = link.get('href', '')
                if not href.startswith('http'):
                    href = self.BASE_URL + href
                car['url'] = href
                id_match = re.search(r'/(\d+)/?$|id[=-](\d+)', href)
                if id_match:
                    car['external_id'] = id_match.group(1) or id_match.group(2)

        if 'external_id' not in car:
            car['external_id'] = str(hash(str(listing)[:200]))

        if 'url' not in car:
            link = listing.find('a', href=re.compile(r'pkw\.de'))
            if link:
                href = link.get('href', '')
                car['url'] = href if href.startswith('http') else self.BASE_URL + href

        title_el = listing.find(['h2', 'h3', 'h4'], class_=re.compile(r'title|name|heading', re.I))
        if not title_el:
            title_el = listing.find('a', href=re.compile(r'/auto/'))
        car['title'] = title_el.get_text(strip=True) if title_el else ''

        car['brand'], car['model'] = self._extract_brand_model(car['title'])

        price_el = listing.find(string=re.compile(r'[\d\.]+\s*€'))
        if not price_el:
            price_el = listing.find(class_=re.compile(r'price', re.I))
        if price_el:
            car['price'] = self._parse_price(
                price_el.get_text(strip=True) if hasattr(price_el, 'get_text') else str(price_el)
            )

        img = listing.find('img', src=re.compile(r'https?://'))
        if not img:
            img = listing.find('img', attrs={'data-src': re.compile(r'https?://')})
        if img:
            car['image_url'] = img.get('src') or img.get('data-src', '')

        car['images'] = []
        for img_tag in listing.find_all('img', src=re.compile(r'https?://')):
            url = img_tag.get('src', '')
            if url and 'logo' not in url.lower():
                car['images'].append(url)

        text = listing.get_text(' ', strip=True)
        km = re.search(r'([\d\.]+)\s*km', text, re.I)
        if km:
            car['mileage'] = self._parse_mileage(km.group(1))
        yr = re.search(r'EZ\s*(\d{2})/(\d{4})|(\d{2})/(\d{4})', text)
        if yr:
            car['year'] = int(yr.group(2) or yr.group(4))
        for pat, fuel in {'Benzin': 'Benzin', 'Diesel': 'Diesel', 'Elektro': 'Elektro', 'Hybrid': 'Hybrid'}.items():
            if pat.lower() in text.lower():
                car['fuel_type'] = fuel
                break
        ps = re.search(r'(\d+)\s*PS|(\d+)\s*kW', text)
        if ps:
            car['power'] = ps.group(0)
        loc = listing.find(class_=re.compile(r'location|city|place', re.I))
        if loc:
            car['location'] = loc.get_text(strip=True)

        return car

    def _extract_brand_model(self, title):
        if not title:
            return '', ''
        tl = title.lower()
        for brand_name in sorted(BRAND_SLUGS.keys(), key=len, reverse=True):
            if brand_name in tl:
                rest = title[tl.index(brand_name) + len(brand_name):].strip(' -,')
                model = rest.split(',')[0].strip() if ',' in rest else rest.split(' ')[0].strip()
                return brand_name.title(), model
        parts = title.split(' ', 1)
        return parts[0] if parts else '', (parts[1].split(',')[0].strip() if len(parts) > 1 else '')
