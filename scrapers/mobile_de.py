import re
import json
import logging
from urllib.parse import urlencode
from bs4 import BeautifulSoup
from .base import BaseScraper

logger = logging.getLogger(__name__)

# Mobile.de Marken-IDs für URL-Parameter
BRAND_IDS = {
    'audi': '1900', 'bmw': '3500', 'mercedes-benz': '17200', 'volkswagen': '25200',
    'opel': '19000', 'ford': '9000', 'porsche': '20100', 'toyota': '24100',
    'honda': '11000', 'hyundai': '11600', 'kia': '12600', 'mazda': '16800',
    'nissan': '18700', 'peugeot': '19300', 'renault': '20700', 'seat': '22500',
    'skoda': '22900', 'volvo': '25100', 'fiat': '8800', 'citroen': '5900',
    'mini': '17600', 'tesla': '67691', 'smart': '22700', 'mitsubishi': '17700',
    'suzuki': '23600', 'dacia': '6600', 'land rover': '14600', 'jaguar': '12400',
    'alfa romeo': '900', 'chevrolet': '5600', 'jeep': '12300', 'subaru': '23400',
    'lexus': '15400', 'cupra': '84789', 'seat': '22500', 'peugeot': '19300',
}

FUEL_MAP = {
    'benzin': 'PETROL', 'diesel': 'DIESEL', 'elektro': 'ELECTRICITY',
    'hybrid': 'HYBRID', 'gas': 'LPG', 'plug-in-hybrid': 'HYBRID_PLUGIN',
}


class MobileDeScraper(BaseScraper):
    """
    Scraper für Mobile.de.
    Strategie 1: Eingebettetes JSON in der HTML-Seite (window.__STATE__ / script-Tags)
    Strategie 2: JSON-API mit Accept: application/json Header
    Strategie 3: HTML-Fallback mit mehreren Selektoren
    """

    SEARCH_URL = 'https://suchen.mobile.de/fahrzeuge/search.html'
    PLATFORM = 'mobile_de'

    def search(self, brand=None, model=None, price_min=None, price_max=None,
               year_min=None, mileage_max=None, fuel_type=None, page=1):
        params = {
            'lang': 'de',
            'pageNumber': page,
            'sortOption.sortBy': 'creationDate',
            'sortOption.sortOrder': 'DESCENDING',
            'isSearchRequest': 'true',
        }

        if brand:
            brand_key = brand.lower()
            if brand_key in BRAND_IDS:
                params['makeModelVariant1.makeId'] = BRAND_IDS[brand_key]

        if price_min:
            params['minPrice'] = price_min
        if price_max:
            params['maxPrice'] = price_max
        if year_min:
            params['minFirstRegistrationDate'] = f'{year_min}-01-01'
        if mileage_max:
            params['maxMileage'] = mileage_max
        if fuel_type and fuel_type.lower() in FUEL_MAP:
            params['fuelTypes'] = FUEL_MAP[fuel_type.lower()]

        url = f'{self.SEARCH_URL}?{urlencode(params)}'
        logger.info(f"Mobile.de Suche: {url}")

        # Strategie 1: JSON-API (Accept: application/json)
        results = self._try_json_api(url)
        if results:
            logger.info(f"Mobile.de JSON-API: {len(results)} Ergebnisse")
            return results

        # Strategie 2: HTML mit eingebettetem JSON
        response = self._request(url)
        if not response:
            return []

        results = self._try_embedded_json(response.text)
        if results:
            logger.info(f"Mobile.de Embedded JSON: {len(results)} Ergebnisse")
            return results

        # Strategie 3: HTML-Parsing
        results = self._parse_html(response.text)
        logger.info(f"Mobile.de HTML-Fallback: {len(results)} Ergebnisse")
        return results

    # ------------------------------------------------------------------ #
    #  Strategie 1: JSON-API                                               #
    # ------------------------------------------------------------------ #
    def _try_json_api(self, url):
        """Versucht mobile.de als JSON-API aufzurufen."""
        import time, random
        time.sleep(random.uniform(self.delay_min, self.delay_max))
        try:
            headers = self._get_headers()
            headers.update({
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': 'https://suchen.mobile.de/',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
            })
            resp = self.session.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                ct = resp.headers.get('Content-Type', '')
                if 'json' in ct:
                    data = resp.json()
                    return self._parse_json_response(data)
        except Exception as e:
            logger.debug(f"JSON-API fehlgeschlagen: {e}")
        return []

    def _parse_json_response(self, data):
        """Parst eine JSON-Antwort von mobile.de."""
        results = []
        # Mögliche Strukturen je nach API-Version
        items = (
            data.get('searchResultItems') or
            data.get('items') or
            data.get('ads') or
            data.get('listings') or
            (data.get('data') or {}).get('listings') or
            []
        )
        for item in items:
            try:
                car = self._parse_json_item(item)
                if car:
                    results.append(car)
            except Exception as e:
                logger.debug(f"JSON-Item-Fehler: {e}")
        return results

    def _parse_json_item(self, item):
        """Einzelnes JSON-Inserat von mobile.de parsen."""
        car = {'platform': self.PLATFORM}

        # ID
        car['external_id'] = str(
            item.get('id') or item.get('adId') or item.get('vehicleId') or ''
        )
        if not car['external_id']:
            return None

        # Titel / Marke / Modell
        car['title'] = (
            item.get('title') or
            item.get('name') or
            f"{item.get('make', {}).get('name','') if isinstance(item.get('make'), dict) else item.get('make','')}"
            f" {item.get('model', {}).get('name','') if isinstance(item.get('model'), dict) else item.get('model','')}".strip()
        )

        def _nested(obj, *keys):
            for k in keys:
                if isinstance(obj, dict):
                    obj = obj.get(k)
                else:
                    return None
            return obj

        car['brand'] = (
            _nested(item, 'make', 'name') or item.get('make') or ''
        )
        car['model'] = (
            _nested(item, 'model', 'name') or item.get('model') or ''
        )

        # Preis
        price_raw = (
            _nested(item, 'price', 'amount') or
            _nested(item, 'price', 'value') or
            item.get('price') or
            item.get('priceRaw')
        )
        if price_raw:
            car['price'] = self._parse_price(str(price_raw))

        # Kilometerstand
        km = (
            _nested(item, 'mileage', 'value') or
            item.get('mileage') or
            item.get('kilometerstand')
        )
        if km:
            car['mileage'] = self._parse_mileage(str(km))

        # Baujahr
        year = (
            item.get('firstRegistrationYear') or
            _nested(item, 'firstRegistration', 'year') or
            item.get('year') or
            item.get('baujahr')
        )
        if year:
            try:
                car['year'] = int(str(year)[:4])
            except Exception:
                pass

        # Kraftstoff
        car['fuel_type'] = (
            _nested(item, 'fuelType', 'name') or
            item.get('fuelType') or
            item.get('kraftstoff') or ''
        )

        # Leistung
        ps = (
            _nested(item, 'power', 'ps') or
            _nested(item, 'enginePower', 'ps') or
            item.get('power')
        )
        if ps:
            car['power'] = f"{ps} PS"

        # Getriebe
        car['transmission'] = (
            _nested(item, 'transmission', 'name') or
            item.get('transmission') or ''
        )

        # Farbe
        car['color'] = (
            _nested(item, 'color', 'name') or
            item.get('color') or ''
        )

        # Standort
        loc = item.get('location') or item.get('seller', {})
        if isinstance(loc, dict):
            car['location'] = loc.get('city') or loc.get('zip') or ''
        elif isinstance(loc, str):
            car['location'] = loc

        # Verkäufer
        seller = item.get('seller') or {}
        if isinstance(seller, dict):
            car['seller_name'] = seller.get('name') or seller.get('companyName') or ''
            car['seller_type'] = 'Händler' if seller.get('isDealer') else 'Privat'

        # URL
        url_path = item.get('url') or item.get('detailPageUrl') or ''
        if url_path and not url_path.startswith('http'):
            url_path = 'https://suchen.mobile.de' + url_path
        car['url'] = url_path

        # Bilder
        images = item.get('images') or item.get('imageUrls') or []
        if isinstance(images, list):
            car['images'] = [
                (img.get('url') if isinstance(img, dict) else img)
                for img in images[:20]
            ]
            car['images'] = [u for u in car['images'] if u and isinstance(u, str)]
        if not car.get('image_url') and car.get('images'):
            car['image_url'] = car['images'][0]

        # Thumbnail als Fallback
        thumb = (
            item.get('thumbnailUrl') or
            item.get('imageUrl') or
            _nested(item, 'images', 0, 'url') if item.get('images') else None
        )
        if thumb and not car.get('image_url'):
            car['image_url'] = thumb if isinstance(thumb, str) else ''

        return car if car.get('external_id') else None

    # ------------------------------------------------------------------ #
    #  Strategie 2: Eingebettetes JSON                                     #
    # ------------------------------------------------------------------ #
    def _try_embedded_json(self, html):
        """Sucht nach JSON-Daten in <script>-Tags der Seite."""
        results = []

        # Pattern: window.__INITIAL_STATE__ = {...}
        patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*({.+?})(?:;|\n)',
            r'window\.__STATE__\s*=\s*({.+?})(?:;|\n)',
            r'window\.INIT_DATA\s*=\s*({.+?})(?:;|\n)',
            r'"searchResults"\s*:\s*(\[.+?\])\s*[,}]',
            r'"listings"\s*:\s*(\[.+?\])\s*[,}]',
            r'"vehicles"\s*:\s*(\[.+?\])\s*[,}]',
            r'"ads"\s*:\s*(\[.+?\])\s*[,}]',
        ]

        for pattern in patterns:
            try:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    raw = match.group(1)
                    data = json.loads(raw)
                    if isinstance(data, list) and len(data) > 0:
                        parsed = self._parse_json_response({'items': data})
                        if parsed:
                            return parsed
                    elif isinstance(data, dict):
                        parsed = self._parse_json_response(data)
                        if parsed:
                            return parsed
            except Exception:
                continue

        # Script-Tags mit type="application/json"
        soup = BeautifulSoup(html, 'html5lib')
        for script in soup.find_all('script', type='application/json'):
            try:
                data = json.loads(script.string or '')
                parsed = self._parse_json_response(data)
                if parsed:
                    return parsed
            except Exception:
                continue

        # __NEXT_DATA__ (falls Next.js)
        next_script = soup.find('script', id='__NEXT_DATA__')
        if next_script:
            try:
                data = json.loads(next_script.string or '')
                listings = self._deep_find_listings(data)
                if listings:
                    parsed = self._parse_json_response({'items': listings})
                    if parsed:
                        return parsed
            except Exception:
                pass

        return results

    def _deep_find_listings(self, obj, depth=0):
        """Sucht rekursiv nach einem Listen-Schlüssel mit Fahrzeugdaten."""
        if depth > 6 or not isinstance(obj, dict):
            return None
        for key in ('listings', 'vehicles', 'ads', 'items', 'results', 'searchResults'):
            if key in obj and isinstance(obj[key], list) and len(obj[key]) > 0:
                return obj[key]
        for v in obj.values():
            if isinstance(v, dict):
                found = self._deep_find_listings(v, depth + 1)
                if found:
                    return found
        return None

    # ------------------------------------------------------------------ #
    #  Strategie 3: HTML-Parsing                                          #
    # ------------------------------------------------------------------ #
    def _parse_html(self, html):
        """HTML-Fallback: Parst mobile.de Suchergebnisse aus dem DOM."""
        soup = BeautifulSoup(html, 'html5lib')
        results = []

        # Verschiedene Selektoren für aktuelle + ältere mobile.de Layouts
        listings = (
            soup.select('[data-testid="result-listing-ad"]') or
            soup.select('[data-testid="result-listing"]') or
            soup.select('article.u-clearfix') or
            soup.select('.cBox-body--resultitem') or
            soup.select('[class*="result-listing"]') or
            soup.select('div[data-ad-id]') or
            soup.select('li[data-ad-id]') or
            []
        )

        # Generischer Fallback: Links auf Detailseiten
        if not listings:
            detail_links = soup.find_all(
                'a', href=re.compile(r'/fahrzeuge/details\.html|suchen\.mobile\.de/fahrzeuge/details')
            )
            seen_parents = set()
            for link in detail_links:
                parent = link.find_parent(['article', 'li', 'div'])
                if parent and id(parent) not in seen_parents:
                    seen_parents.add(id(parent))
                    listings.append(parent)

        for listing in listings[:30]:
            try:
                car = self._parse_html_item(listing)
                if car and car.get('title') and car.get('external_id'):
                    results.append(car)
            except Exception as e:
                logger.debug(f"HTML-Item Fehler: {e}")

        return results

    def _parse_html_item(self, el):
        """Einzelnes HTML-Listenelement parsen."""
        car = {'platform': self.PLATFORM}

        # ID aus data-Attributen
        car['external_id'] = (
            el.get('data-ad-id') or
            el.get('data-testid-ad-id') or
            el.get('id', '').replace('listing-', '') or
            ''
        )

        # Link
        link = el.find('a', href=re.compile(r'/fahrzeuge/details|mobile\.de/auto'))
        if not link:
            link = el.find('a', href=True)
        if link:
            href = link.get('href', '')
            if href and not href.startswith('http'):
                href = 'https://suchen.mobile.de' + href
            car['url'] = href

            if not car['external_id']:
                m = re.search(r'[?&]id=(\d+)|/(\d+)\.html', href)
                if m:
                    car['external_id'] = m.group(1) or m.group(2)

        if not car['external_id']:
            car['external_id'] = str(abs(hash(el.get_text()[:100])))

        # Titel
        for sel in ['h2', 'h3', '[data-testid*="title"]', '.u-text-break-word', '.heading']:
            title_el = el.select_one(sel)
            if title_el:
                car['title'] = title_el.get_text(strip=True)
                break
        if not car.get('title') and link:
            car['title'] = link.get_text(strip=True)

        # Marke + Modell aus Titel
        car['brand'], car['model'] = self._extract_brand_model(car.get('title', ''))

        # Preis
        for sel in ['[data-testid*="price"]', '.price-block', '[class*="price"]']:
            pel = el.select_one(sel)
            if pel:
                car['price'] = self._parse_price(pel.get_text(strip=True))
                if car['price']:
                    break
        if not car.get('price'):
            pm = re.search(r'([\d.,]+)\s*(?:€|EUR)', el.get_text())
            if pm:
                car['price'] = self._parse_price(pm.group(1))

        # Bild
        img = el.find('img', src=re.compile(r'https?://'))
        if not img:
            img = el.find('img', attrs={'data-src': re.compile(r'https?://')})
        if img:
            car['image_url'] = img.get('src') or img.get('data-src') or ''
            car['images'] = [car['image_url']] if car['image_url'] else []

        # Detailtext für KM, Jahr, Kraftstoff, PS
        text = el.get_text(' ', strip=True)

        km_m = re.search(r'([\d.]+)\s*km', text, re.I)
        if km_m:
            car['mileage'] = self._parse_mileage(km_m.group(1))

        year_m = re.search(r'EZ\s*(\d{2})/(\d{4})|(\d{2})/(\d{4})', text)
        if year_m:
            car['year'] = int(year_m.group(2) or year_m.group(4))

        for kw, label in [('Benzin', 'Benzin'), ('Diesel', 'Diesel'),
                          ('Elektro', 'Elektro'), ('Hybrid', 'Hybrid'), ('Erdgas', 'Gas')]:
            if kw.lower() in text.lower():
                car['fuel_type'] = label
                break

        ps_m = re.search(r'(\d+)\s*PS', text)
        if ps_m:
            car['power'] = ps_m.group(0)

        # Getriebe
        if 'Automatik' in text:
            car['transmission'] = 'Automatik'
        elif 'Schaltgetriebe' in text or 'Schalt' in text:
            car['transmission'] = 'Schaltgetriebe'

        # Standort
        for sel in ['[data-testid*="seller-location"]', '.seller-address', '[class*="location"]', '.city']:
            loc_el = el.select_one(sel)
            if loc_el:
                car['location'] = loc_el.get_text(strip=True)
                break

        return car

    # _extract_brand_model inherited from BaseScraper (base.py)
