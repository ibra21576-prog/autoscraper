"""
Scraper für Autohero.com
Autohero nutzt eine interne REST-API — wir rufen sie direkt ab.
"""
import re
import json
import logging
from urllib.parse import urlencode
from .base import BaseScraper

logger = logging.getLogger(__name__)

BRAND_FILTER = {
    'audi': 'AUDI', 'bmw': 'BMW', 'mercedes-benz': 'MERCEDES_BENZ',
    'volkswagen': 'VOLKSWAGEN', 'opel': 'OPEL', 'ford': 'FORD',
    'porsche': 'PORSCHE', 'toyota': 'TOYOTA', 'hyundai': 'HYUNDAI',
    'kia': 'KIA', 'skoda': 'SKODA', 'seat': 'SEAT', 'renault': 'RENAULT',
    'peugeot': 'PEUGEOT', 'fiat': 'FIAT', 'volvo': 'VOLVO',
    'mazda': 'MAZDA', 'honda': 'HONDA', 'nissan': 'NISSAN',
    'mini': 'MINI', 'tesla': 'TESLA', 'dacia': 'DACIA',
    'citroen': 'CITROEN', 'suzuki': 'SUZUKI', 'land rover': 'LAND_ROVER',
    'lexus': 'LEXUS', 'jaguar': 'JAGUAR', 'mitsubishi': 'MITSUBISHI',
}


class AutoheroScraper(BaseScraper):
    """Scraper für Autohero.com über ihre öffentliche API."""

    API_URL = 'https://api.autohero.com/v1/cars'
    PLATFORM = 'autohero'

    def _get_headers(self):
        h = super()._get_headers()
        h['Accept'] = 'application/json'
        h['Origin'] = 'https://www.autohero.com'
        h['Referer'] = 'https://www.autohero.com/'
        return h

    def search(self, brand=None, model=None, price_min=None, price_max=None,
               year_min=None, mileage_max=None, fuel_type=None, page=1):
        """Suche über die Autohero API."""
        params = {
            'country': 'de',
            'language': 'de',
            'size': 24,
            'page': page - 1,
            'sort': 'listed_desc',
        }

        if brand:
            brand_key = BRAND_FILTER.get(brand.lower())
            if brand_key:
                params['makeKey'] = brand_key
        if model:
            params['modelKey'] = model.upper().replace(' ', '_')
        if price_min:
            params['priceFrom'] = price_min
        if price_max:
            params['priceTo'] = price_max
        if year_min:
            params['firstRegistrationYearFrom'] = year_min
        if mileage_max:
            params['mileageTo'] = mileage_max
        if fuel_type:
            fuel_map = {'benzin': 'PETROL', 'diesel': 'DIESEL', 'elektro': 'ELECTRIC', 'hybrid': 'HYBRID'}
            if fuel_type.lower() in fuel_map:
                params['fuelType'] = fuel_map[fuel_type.lower()]

        url = f'{self.API_URL}?{urlencode(params)}'
        logger.info(f"Autohero API: {url}")

        response = self._request(url)
        if not response:
            return []

        try:
            data = response.json()
            items = data.get('cars', data.get('items', data.get('results', [])))
            if not items and isinstance(data, list):
                items = data
            return [self._parse_item(item) for item in items if isinstance(item, dict)]
        except Exception as e:
            logger.error(f"Autohero JSON parse error: {e}")
            return []

    def _parse_item(self, item):
        """API-Item zu einheitlichem Auto-Dict konvertieren."""
        car = {'platform': self.PLATFORM}

        car['external_id'] = str(item.get('id', item.get('stockNumber', hash(str(item)[:100]))))

        car_id = item.get('id', item.get('stockNumber', ''))
        if car_id:
            car['url'] = f'https://www.autohero.com/de/details/{car_id}/'
        else:
            car['url'] = 'https://www.autohero.com'

        make = item.get('make', {})
        model_obj = item.get('model', {})

        if isinstance(make, dict):
            car['brand'] = make.get('name', make.get('key', ''))
        else:
            car['brand'] = str(make)

        if isinstance(model_obj, dict):
            car['model'] = model_obj.get('name', model_obj.get('key', ''))
        else:
            car['model'] = str(model_obj)

        car['title'] = item.get('title') or f"{car['brand']} {car['model']}".strip()
        car['title'] = car['title'] or item.get('name', '')

        car['price'] = item.get('pricing', {}).get('amountMinorUnits', None)
        if car['price']:
            car['price'] = car['price'] // 100
        if not car['price']:
            car['price'] = item.get('price', item.get('retailPrice'))
            if isinstance(car['price'], dict):
                car['price'] = car['price'].get('amount')
            if car['price']:
                car['price'] = int(car['price'])

        car['mileage'] = item.get('mileage', item.get('km'))
        car['year'] = item.get('firstRegistrationYear', item.get('year'))

        fuel = item.get('fuelType', item.get('fuel', ''))
        if isinstance(fuel, dict):
            fuel = fuel.get('name', '')
        fuel_map = {'PETROL': 'Benzin', 'DIESEL': 'Diesel', 'ELECTRIC': 'Elektro', 'HYBRID': 'Hybrid',
                    'Petrol': 'Benzin', 'Diesel': 'Diesel', 'Electric': 'Elektro'}
        car['fuel_type'] = fuel_map.get(str(fuel), str(fuel))

        power = item.get('power', {})
        if isinstance(power, dict):
            ps = power.get('ps', power.get('kw'))
            unit = 'PS' if 'ps' in power else 'kW'
            if ps:
                car['power'] = f"{ps} {unit}"
        elif power:
            car['power'] = str(power)

        trans = item.get('transmission', item.get('gearbox', ''))
        if isinstance(trans, dict):
            trans = trans.get('name', '')
        car['transmission'] = str(trans) if trans else ''

        color = item.get('color', item.get('exteriorColor', {}))
        if isinstance(color, dict):
            color = color.get('name', '')
        car['color'] = str(color) if color else ''

        car['description'] = item.get('highlights', item.get('description', ''))
        if isinstance(car['description'], list):
            car['description'] = ' | '.join(car['description'])

        location = item.get('location', item.get('seller', {}))
        if isinstance(location, dict):
            city = location.get('city', location.get('name', ''))
            car['location'] = str(city) if city else ''
        elif location:
            car['location'] = str(location)

        # Bilder
        images = item.get('images', item.get('photos', item.get('imageUrls', [])))
        if isinstance(images, list):
            img_urls = []
            for img in images:
                if isinstance(img, dict):
                    u = img.get('url', img.get('src', img.get('uri', '')))
                    if u:
                        img_urls.append(str(u))
                elif isinstance(img, str):
                    img_urls.append(img)
            car['images'] = img_urls[:20]
            car['image_url'] = img_urls[0] if img_urls else ''
        else:
            car['images'] = []
            car['image_url'] = str(images) if images else ''

        return car
