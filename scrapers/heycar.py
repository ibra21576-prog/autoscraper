"""
Scraper für heycar.com (Volkswagen Group Plattform).
Nutzt deren GraphQL / Search-API.
"""
import re
import json
import logging
from urllib.parse import urlencode
from .base import BaseScraper

logger = logging.getLogger(__name__)

BRAND_SLUGS = {
    'audi': 'audi', 'bmw': 'bmw', 'mercedes-benz': 'mercedes-benz', 'volkswagen': 'volkswagen',
    'opel': 'opel', 'ford': 'ford', 'porsche': 'porsche', 'toyota': 'toyota',
    'hyundai': 'hyundai', 'kia': 'kia', 'skoda': 'skoda', 'seat': 'seat',
    'renault': 'renault', 'peugeot': 'peugeot', 'fiat': 'fiat', 'volvo': 'volvo',
    'mazda': 'mazda', 'honda': 'honda', 'nissan': 'nissan', 'mini': 'mini',
    'cupra': 'cupra', 'dacia': 'dacia', 'citroen': 'citroen', 'suzuki': 'suzuki',
    'land rover': 'land-rover', 'lexus': 'lexus', 'mitsubishi': 'mitsubishi',
}


class HeycarScraper(BaseScraper):
    """Scraper für heycar.com Fahrzeugangebote."""

    BASE_URL = 'https://heycar.com'
    PLATFORM = 'heycar'

    def _get_headers(self):
        h = super()._get_headers()
        h['Accept'] = 'text/html,application/xhtml+xml'
        h['Referer'] = 'https://heycar.com/'
        return h

    def search(self, brand=None, model=None, price_min=None, price_max=None,
               year_min=None, mileage_max=None, fuel_type=None, page=1):
        """Suche auf heycar.com."""
        params = {
            'sort': 'published_desc',
            'cy': 'de',
        }

        path = '/de/suche'
        if brand:
            slug = BRAND_SLUGS.get(brand.lower(), brand.lower().replace(' ', '-'))
            path += f'/{slug}'

        if price_min:
            params['priceFrom'] = price_min
        if price_max:
            params['priceTo'] = price_max
        if year_min:
            params['yearFrom'] = year_min
        if mileage_max:
            params['mileageTo'] = mileage_max
        if fuel_type:
            fuel_map = {'benzin': 'petrol', 'diesel': 'diesel', 'elektro': 'electric', 'hybrid': 'hybrid'}
            if fuel_type.lower() in fuel_map:
                params['fuelType'] = fuel_map[fuel_type.lower()]
        if page > 1:
            params['page'] = page

        url = f'{self.BASE_URL}{path}?{urlencode(params)}'
        logger.info(f"heycar search: {url}")

        response = self._request(url)
        if not response:
            return []

        # Versuche zuerst JSON aus Next.js __NEXT_DATA__
        results = self._try_next_data(response.text)
        if results:
            return results

        return self._parse_html(response.text)

    def _try_next_data(self, html):
        """Extrahiere Fahrzeugdaten aus Next.js JSON."""
        try:
            match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
            if not match:
                return []

            data = json.loads(match.group(1))
            listings = (
                data.get('props', {}).get('pageProps', {}).get('listings', [])
                or data.get('props', {}).get('pageProps', {}).get('vehicles', [])
                or data.get('props', {}).get('pageProps', {}).get('cars', [])
                or data.get('props', {}).get('pageProps', {}).get('data', {}).get('listings', [])
            )

            if not listings:
                # Tiefer suchen
                def find_listings(obj, depth=0):
                    if depth > 6 or not isinstance(obj, dict):
                        return []
                    for k, v in obj.items():
                        if k in ('listings', 'vehicles', 'cars', 'results') and isinstance(v, list) and v:
                            return v
                        found = find_listings(v, depth + 1)
                        if found:
                            return found
                    return []
                listings = find_listings(data)

            return [self._parse_json_item(item) for item in listings if isinstance(item, dict)]
        except Exception as e:
            logger.debug(f"heycar Next.js parse error: {e}")
            return []

    def _parse_json_item(self, item):
        """JSON-Item zu einheitlichem Format konvertieren."""
        car = {'platform': self.PLATFORM}

        car['external_id'] = str(item.get('id', item.get('uuid', item.get('listingId', hash(str(item)[:100])))))

        slug = item.get('slug') or item.get('url') or ''
        if slug:
            car['url'] = f"{self.BASE_URL}/de/angebote/{slug}" if not slug.startswith('http') else slug
        else:
            car['url'] = f"{self.BASE_URL}/de/suche"

        car['brand'] = item.get('make', item.get('brand', item.get('manufacturer', '')))
        if isinstance(car['brand'], dict):
            car['brand'] = car['brand'].get('name', '')

        car['model'] = item.get('model', '')
        if isinstance(car['model'], dict):
            car['model'] = car['model'].get('name', '')

        car['title'] = item.get('title', '') or f"{car['brand']} {car['model']}".strip()

        price = item.get('price', item.get('priceGross', item.get('retailPrice', 0)))
        if isinstance(price, dict):
            price = price.get('amount', price.get('value', 0))
        car['price'] = int(price) if price else None

        car['mileage'] = item.get('mileage', item.get('km'))
        car['year'] = item.get('year', item.get('firstRegistrationYear'))

        fuel = item.get('fuelType', item.get('fuel', ''))
        if isinstance(fuel, dict):
            fuel = fuel.get('name', fuel.get('id', ''))
        fuel_map = {'petrol': 'Benzin', 'diesel': 'Diesel', 'electric': 'Elektro', 'hybrid': 'Hybrid',
                    'PETROL': 'Benzin', 'DIESEL': 'Diesel', 'ELECTRIC': 'Elektro', 'HYBRID': 'Hybrid'}
        car['fuel_type'] = fuel_map.get(str(fuel), str(fuel))

        power = item.get('power', item.get('enginePower'))
        if isinstance(power, dict):
            ps = power.get('ps', power.get('kw'))
            if ps:
                car['power'] = f"{ps} PS"
        elif power:
            car['power'] = str(power)

        car['transmission'] = str(item.get('gearbox', item.get('transmission', '')))
        car['color'] = str(item.get('color', item.get('exteriorColor', {}))).replace('{', '').replace('}', '')

        location = item.get('location', item.get('seller', {}))
        if isinstance(location, dict):
            car['location'] = location.get('city', location.get('name', ''))
        elif location:
            car['location'] = str(location)

        images = item.get('images', item.get('photos', []))
        if isinstance(images, list):
            img_urls = []
            for img in images:
                if isinstance(img, dict):
                    u = img.get('url', img.get('src', ''))
                    if u:
                        img_urls.append(u)
                elif isinstance(img, str):
                    img_urls.append(img)
            car['images'] = img_urls[:20]
            car['image_url'] = img_urls[0] if img_urls else ''

        return car

    def _parse_html(self, html):
        """Fallback: HTML parsen."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html5lib')
        results = []

        listings = soup.select('[data-qa-id*="listing"]') or soup.select('article') or soup.select('.vehicle-card')
        for listing in listings:
            try:
                car = {'platform': self.PLATFORM}
                car['external_id'] = str(hash(str(listing)[:200]))

                link = listing.find('a', href=re.compile(r'/de/angebote/|/offers/'))
                if link:
                    href = link.get('href', '')
                    car['url'] = href if href.startswith('http') else self.BASE_URL + href
                    id_match = re.search(r'/(\d+)/?', href)
                    if id_match:
                        car['external_id'] = id_match.group(1)

                title_el = listing.find(['h2', 'h3', 'a'])
                car['title'] = title_el.get_text(strip=True) if title_el else ''

                price_el = listing.find(string=re.compile(r'[\d\.]+\s*€'))
                if price_el:
                    car['price'] = self._parse_price(str(price_el))

                img = listing.find('img', src=re.compile(r'https?://'))
                if img:
                    car['image_url'] = img.get('src', '')
                    car['images'] = [car['image_url']]

                text = listing.get_text(' ', strip=True)
                km = re.search(r'([\d\.]+)\s*km', text)
                if km:
                    car['mileage'] = self._parse_mileage(km.group(1))
                yr = re.search(r'(\d{4})', text)
                if yr:
                    year_val = int(yr.group(1))
                    if 2000 <= year_val <= 2026:
                        car['year'] = year_val

                if car.get('title'):
                    results.append(car)
            except Exception as e:
                logger.debug(f"heycar HTML parse error: {e}")

        logger.info(f"heycar: {len(results)} Ergebnisse (HTML)")
        return results
