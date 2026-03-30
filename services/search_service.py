import logging
from datetime import datetime
from models import db, Car, CarImage, PriceHistory
from scrapers.mobile_de import MobileDeScraper
from scrapers.autoscout24 import AutoScout24Scraper
from scrapers.kleinanzeigen import KleinanzeigenScraper
from scrapers.pkw_de import PkwDeScraper
from scrapers.autohero import AutoheroScraper
from scrapers.heycar import HeycarScraper

logger = logging.getLogger(__name__)

mobile_scraper = MobileDeScraper()
autoscout_scraper = AutoScout24Scraper()
kleinanzeigen_scraper = KleinanzeigenScraper()
pkw_scraper = PkwDeScraper()
autohero_scraper = AutoheroScraper()
heycar_scraper = HeycarScraper()

ALL_PLATFORMS = ['mobile_de', 'autoscout24', 'kleinanzeigen', 'pkw_de', 'autohero', 'heycar']


def search_cars(brand=None, model=None, price_min=None, price_max=None,
                year_min=None, mileage_max=None, fuel_type=None,
                platforms=None, page=1):
    """Suche auf allen ausgewählten Plattformen durchführen."""
    if platforms is None:
        platforms = ALL_PLATFORMS

    all_results = []
    scraper_map = {
        'mobile_de': mobile_scraper,
        'autoscout24': autoscout_scraper,
        'kleinanzeigen': kleinanzeigen_scraper,
        'pkw_de': pkw_scraper,
        'autohero': autohero_scraper,
        'heycar': heycar_scraper,
    }

    for platform, scraper in scraper_map.items():
        if platform in platforms:
            try:
                results = scraper.search(
                    brand=brand, model=model, price_min=price_min, price_max=price_max,
                    year_min=year_min, mileage_max=mileage_max, fuel_type=fuel_type, page=page
                )
                all_results.extend(results)
            except Exception as e:
                logger.error(f"{platform} scraping failed: {e}")

    saved_results = []
    for car_data in all_results:
        car = save_or_update_car(car_data)
        if car:
            saved_results.append(car)

    return saved_results


def save_or_update_car(car_data):
    """Auto in DB speichern oder aktualisieren."""
    try:
        existing = Car.query.filter_by(
            platform=car_data.get('platform'),
            external_id=car_data.get('external_id')
        ).first()

        if existing:
            old_price = existing.price
            existing.title = car_data.get('title', existing.title)
            existing.price = car_data.get('price', existing.price)
            existing.mileage = car_data.get('mileage', existing.mileage)
            existing.year = car_data.get('year', existing.year)
            existing.fuel_type = car_data.get('fuel_type', existing.fuel_type)
            existing.power = car_data.get('power', existing.power)
            existing.transmission = car_data.get('transmission', existing.transmission)
            existing.color = car_data.get('color', existing.color)
            existing.description = car_data.get('description', existing.description)
            existing.seller_name = car_data.get('seller_name', existing.seller_name)
            existing.seller_type = car_data.get('seller_type', existing.seller_type)
            existing.location = car_data.get('location', existing.location)
            existing.image_url = car_data.get('image_url', existing.image_url)
            existing.last_seen = datetime.utcnow()

            if old_price != existing.price and existing.price:
                price_entry = PriceHistory(car_id=existing.id, price=existing.price)
                db.session.add(price_entry)

            db.session.commit()
            return existing
        else:
            car = Car(
                platform=car_data.get('platform'),
                external_id=car_data.get('external_id'),
                title=car_data.get('title'),
                brand=car_data.get('brand'),
                model=car_data.get('model'),
                price=car_data.get('price'),
                mileage=car_data.get('mileage'),
                year=car_data.get('year'),
                fuel_type=car_data.get('fuel_type'),
                power=car_data.get('power'),
                transmission=car_data.get('transmission'),
                color=car_data.get('color'),
                description=car_data.get('description'),
                seller_name=car_data.get('seller_name'),
                seller_type=car_data.get('seller_type'),
                location=car_data.get('location'),
                url=car_data.get('url'),
                image_url=car_data.get('image_url'),
            )
            db.session.add(car)
            db.session.flush()

            # Bilder speichern
            image_urls = car_data.get('images', [])
            if car_data.get('image_url') and car_data['image_url'] not in image_urls:
                image_urls.insert(0, car_data['image_url'])
            for idx, img_url in enumerate(image_urls[:20]):
                img = CarImage(car_id=car.id, image_url=img_url, position=idx)
                db.session.add(img)

            if car.price:
                price_entry = PriceHistory(car_id=car.id, price=car.price)
                db.session.add(price_entry)

            db.session.commit()
            return car
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to save car: {e}")
        return None
