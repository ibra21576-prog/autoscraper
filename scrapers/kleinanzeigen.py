import re
import logging
from urllib.parse import urlencode, quote
from bs4 import BeautifulSoup
from .base import BaseScraper

logger = logging.getLogger(__name__)


class KleinanzeigenScraper(BaseScraper):
    """Scraper für Kleinanzeigen.de (ehem. eBay Kleinanzeigen) Fahrzeugangebote."""

    BASE_URL = 'https://www.kleinanzeigen.de'
    PLATFORM = 'kleinanzeigen'

    def search(self, brand=None, model=None, price_min=None, price_max=None,
               year_min=None, mileage_max=None, fuel_type=None, page=1):
        """Suche auf Kleinanzeigen.de durchführen."""
        # Suchbegriff zusammenbauen
        query_parts = []
        if brand:
            query_parts.append(brand)
        if model:
            query_parts.append(model)
        search_query = '+'.join(query_parts) if query_parts else ''

        # URL aufbauen - Kategorie 216 = Autos
        if search_query:
            path = f'/s-autos/{quote(search_query)}/k0c216'
        else:
            path = '/s-autos/k0c216'

        params = {
            'sortingField': 'SORTING_DATE',  # Neueste zuerst
        }

        if price_min:
            params['minPrice'] = price_min
        if price_max:
            params['maxPrice'] = price_max
        if page > 1:
            path = f'/seite:{page}' + path

        url = f'{self.BASE_URL}{path}'
        if params:
            url += '?' + urlencode(params)

        logger.info(f"Kleinanzeigen search: {url}")

        response = self._request(url)
        if not response:
            return []

        return self._parse_results(response.text)

    def _parse_results(self, html):
        """Suchergebnisse aus HTML parsen."""
        soup = BeautifulSoup(html, 'html5lib')
        results = []

        # Kleinanzeigen Listing-Items
        listings = soup.select('[data-adid]')
        if not listings:
            listings = soup.select('article.aditem')
        if not listings:
            listings = soup.select('.ad-listitem')
            listings = [l for l in listings if l.find('a', href=re.compile(r'/s-anzeige/'))]

        for listing in listings:
            try:
                car = self._parse_single(listing)
                if car and car.get('title'):
                    results.append(car)
            except Exception as e:
                logger.debug(f"Failed to parse Kleinanzeigen listing: {e}")
                continue

        logger.info(f"Kleinanzeigen: {len(results)} Ergebnisse gefunden")
        return results

    def _parse_single(self, listing):
        """Einzelnes Listing parsen."""
        car = {'platform': self.PLATFORM}

        # ID
        ad_id = listing.get('data-adid', '')
        if ad_id:
            car['external_id'] = str(ad_id)
        else:
            car['external_id'] = str(hash(str(listing)[:200]))

        # Link
        link = listing.find('a', href=re.compile(r'/s-anzeige/'))
        if link:
            href = link.get('href', '')
            if not href.startswith('http'):
                href = self.BASE_URL + href
            car['url'] = href

        # Titel
        title_el = listing.find(['h2', 'h3', 'a'], class_=re.compile(r'text-module-begin|ellipsis|title', re.I))
        if not title_el and link:
            title_el = link
        car['title'] = title_el.get_text(strip=True) if title_el else ''

        # Marke & Modell aus Titel
        car['brand'], car['model'] = self._extract_brand_model(car['title'])

        # Preis
        price_el = listing.find(class_=re.compile(r'price|aditem-main--middle--price', re.I))
        if not price_el:
            price_el = listing.find(string=re.compile(r'[\d.]+\s*€'))
        if price_el:
            price_text = price_el.get_text(strip=True) if hasattr(price_el, 'get_text') else str(price_el)
            if 'VB' in price_text or '€' in price_text:
                car['price'] = self._parse_price(price_text)

        # Bilder
        img = listing.find('img', src=re.compile(r'https?://'))
        if not img:
            img = listing.find('img', attrs={'data-src': re.compile(r'https?://')})
        if img:
            car['image_url'] = img.get('src') or img.get('data-src', '')
            # Kleinanzeigen nutzt oft kleine Thumbnails - versuche größeres Bild
            if car.get('image_url'):
                car['image_url'] = car['image_url'].replace('/rule:ebapic', '').replace('$_2', '$_57').replace('$_9', '$_57')

        # Alle Bilder sammeln
        car['images'] = []
        all_imgs = listing.find_all('img', src=re.compile(r'https?://.*img\.'))
        for img_tag in all_imgs:
            img_url = img_tag.get('src') or img_tag.get('data-src', '')
            if img_url and 'logo' not in img_url.lower() and 'icon' not in img_url.lower():
                img_url = img_url.replace('$_2', '$_57').replace('$_9', '$_57')
                car['images'].append(img_url)

        # Details aus Text
        details_text = listing.get_text(' ', strip=True)

        # Kilometerstand
        km_match = re.search(r'([\d.]+)\s*km', details_text, re.I)
        if km_match:
            car['mileage'] = self._parse_mileage(km_match.group(1))

        # Baujahr
        year_match = re.search(r'EZ\s*(\d{2})/(\d{4})|(\d{2})/(\d{4})', details_text)
        if year_match:
            car['year'] = int(year_match.group(2) or year_match.group(4))

        # Kraftstoff
        fuel_patterns = {
            'Benzin': 'Benzin', 'Diesel': 'Diesel', 'Elektro': 'Elektro',
            'Hybrid': 'Hybrid', 'Erdgas': 'Gas',
        }
        for pattern, fuel in fuel_patterns.items():
            if pattern.lower() in details_text.lower():
                car['fuel_type'] = fuel
                break

        # Standort
        loc_el = listing.find(class_=re.compile(r'aditem-main--top--left|location', re.I))
        if loc_el:
            car['location'] = loc_el.get_text(strip=True)

        # Seller-Typ
        if 'privat' in details_text.lower():
            car['seller_type'] = 'Privat'
        elif 'gewerblich' in details_text.lower() or 'händler' in details_text.lower():
            car['seller_type'] = 'Händler'

        return car

    def _extract_brand_model(self, title):
        """Marke und Modell aus dem Titel extrahieren."""
        if not title:
            return '', ''

        known_brands = [
            'mercedes-benz', 'mercedes', 'land rover', 'alfa romeo',
            'volkswagen', 'porsche', 'mitsubishi', 'chevrolet',
            'audi', 'bmw', 'opel', 'ford', 'toyota', 'honda', 'hyundai',
            'kia', 'mazda', 'nissan', 'peugeot', 'renault', 'seat',
            'skoda', 'volvo', 'fiat', 'citroen', 'mini', 'tesla',
            'smart', 'suzuki', 'dacia', 'jaguar', 'jeep', 'subaru',
            'lexus', 'cupra',
        ]

        title_lower = title.lower()
        for brand_name in sorted(known_brands, key=len, reverse=True):
            if brand_name in title_lower:
                idx = title_lower.index(brand_name)
                rest = title[idx + len(brand_name):].strip(' -,')
                model_name = rest.split(',')[0].strip() if ',' in rest else rest.split(' ')[0].strip()
                return brand_name.title(), model_name

        parts = title.split(' ', 1)
        return parts[0] if parts else '', parts[1].split(',')[0].strip() if len(parts) > 1 else ''
