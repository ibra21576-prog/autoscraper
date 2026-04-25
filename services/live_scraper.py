import time
import json
import logging
import threading
from datetime import datetime
from queue import Queue

logger = logging.getLogger(__name__)

# Queue für neue Autos (SSE-Stream)
new_cars_queue = Queue()

# Status
scraper_status = {
    'running': False,
    'total_found': 0,
    'last_scrape': None,
    'current_platform': None,
    'errors': [],
}


def live_scraper_loop(app):
    """Hauptschleife des Live-Scrapers. Läuft als Background-Thread."""
    from scrapers.mobile_de import MobileDeScraper
    from scrapers.autoscout24 import AutoScout24Scraper
    from scrapers.kleinanzeigen import KleinanzeigenScraper
    from scrapers.pkw_de import PkwDeScraper
    from scrapers.autohero import AutoheroScraper
    from scrapers.heycar import HeycarScraper
    from models import db, Car, CarImage, PriceHistory

    # Nur Kleinanzeigen — die anderen Plattformen blockieren Scraping
    scrapers = [
        ('kleinanzeigen', KleinanzeigenScraper()),
    ]

    scraper_status['running'] = True
    logger.info("Live-Scraper gestartet")

    interval = app.config.get('LIVE_SCRAPE_INTERVAL', 10)

    while scraper_status['running']:
        for platform_name, scraper in scrapers:
            if not scraper_status['running']:
                break

            scraper_status['current_platform'] = platform_name

            try:
                # Neueste Inserate holen (sortiert nach Datum)
                results = scraper.search(page=1)

                with app.app_context():
                    for car_data in results:
                        try:
                            # "Suche"-Inserate (Gesuche) überspringen
                            title_lower = (car_data.get('title') or '').lower()
                            if (title_lower.startswith('suche ') or
                                    title_lower.startswith('gesuch') or
                                    title_lower.startswith('[suche]') or
                                    'wird gesucht' in title_lower or
                                    ' suche ' in title_lower):
                                continue

                            existing = Car.query.filter_by(
                                platform=car_data.get('platform'),
                                external_id=car_data.get('external_id')
                            ).first()

                            if existing:
                                # Preis-Update prüfen
                                old_price = existing.price
                                existing.price = car_data.get('price', existing.price)
                                existing.last_seen = datetime.utcnow()

                                if old_price != existing.price and existing.price:
                                    price_entry = PriceHistory(car_id=existing.id, price=existing.price)
                                    db.session.add(price_entry)

                                db.session.commit()
                            else:
                                # Neues Auto gefunden
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
                                for idx, img_url in enumerate(image_urls[:20]):  # Max 20 Bilder
                                    img = CarImage(car_id=car.id, image_url=img_url, position=idx)
                                    db.session.add(img)

                                # Preis-History
                                if car.price:
                                    price_entry = PriceHistory(car_id=car.id, price=car.price)
                                    db.session.add(price_entry)

                                db.session.commit()

                                scraper_status['total_found'] += 1

                                # In SSE-Queue pushen
                                car_dict = car.to_dict()
                                new_cars_queue.put(car_dict)

                                logger.info(f"[LIVE] Neues Auto: {car.title} ({car.platform})")

                        except Exception as e:
                            db.session.rollback()
                            logger.debug(f"Fehler beim Speichern: {e}")

                scraper_status['last_scrape'] = datetime.utcnow().strftime('%H:%M:%S')

            except Exception as e:
                error_msg = f"{platform_name}: {str(e)[:100]}"
                scraper_status['errors'] = scraper_status.get('errors', [])[-9:] + [error_msg]
                logger.error(f"Live-Scraper Fehler ({platform_name}): {e}")

            # Warten zwischen Plattformen
            time.sleep(interval)

    scraper_status['running'] = False
    logger.info("Live-Scraper gestoppt")


def _seed_if_empty(app):
    """Befüllt die DB mit Demo-Daten wenn sie komplett leer ist."""
    import time
    time.sleep(3)
    with app.app_context():
        from models import Car
        count = Car.query.count()
        if count == 0:
            logger.info("[LIVE] DB leer — lade Demo-Daten...")
            from services.demo_data import seed_demo_data
            stored, _ = seed_demo_data(app, count=120)
            logger.info(f"[LIVE] {stored} Demo-Fahrzeuge geladen")


def start_live_scraper(app):
    """Live-Scraper als Daemon-Thread starten."""
    # Demo-Seed im Hintergrund falls DB leer
    threading.Thread(target=_seed_if_empty, args=(app,), daemon=True).start()
    thread = threading.Thread(target=live_scraper_loop, args=(app,), daemon=True)
    thread.start()
    logger.info("Live-Scraper Thread gestartet")
    return thread


def stop_live_scraper():
    """Live-Scraper stoppen."""
    scraper_status['running'] = False


def get_scraper_status():
    """Aktuellen Status zurückgeben."""
    return dict(scraper_status)
