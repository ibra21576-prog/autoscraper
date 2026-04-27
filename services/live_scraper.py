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


def _save_and_broadcast(app, car_data):
    """Speichert ein Auto in der DB und pusht es in die SSE-Queue. Gibt Car zurück oder None."""
    from models import db, Car, PriceHistory
    try:
        with app.app_context():
            existing = Car.query.filter_by(
                platform=car_data.get('platform'),
                external_id=car_data.get('external_id')
            ).first()
            if existing:
                return None  # bereits bekannt

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
                seller_type=car_data.get('seller_type'),
                location=car_data.get('location'),
                url=car_data.get('url'),
                image_url=car_data.get('image_url'),
            )
            db.session.add(car)
            db.session.flush()
            if car.price:
                db.session.add(PriceHistory(car_id=car.id, price=car.price))
            db.session.commit()
            new_cars_queue.put(car.to_dict())
            scraper_status['total_found'] += 1
            logger.info(f"[LIVE] Neues Auto: {car.title} ({car.platform})")
            return car
    except Exception as e:
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass
        logger.debug(f"Fehler beim Speichern: {e}")
        return None


def live_scraper_loop(app):
    """
    Hauptschleife des Live-Scrapers.
    Versucht echtes Scraping (Kleinanzeigen). Da Datacenter-IPs geblockt
    werden (403), fällt der Scraper automatisch auf Demo-Simulation zurück:
    alle 30–90 Sekunden erscheint ein neues realistisches Inserat im Feed.
    """
    from scrapers.kleinanzeigen import KleinanzeigenScraper

    scraper = KleinanzeigenScraper()
    scraper_status['running'] = True
    scraper_status['current_platform'] = 'kleinanzeigen'
    logger.info("Live-Scraper gestartet")

    # Demo-Simulation: alle SIM_INTERVAL Sekunden ein neues Auto
    SIM_INTERVAL = 25  # Sekunden zwischen zwei simulierten Inseraten
    last_sim_time = 0
    iteration = 0

    while scraper_status['running']:
        iteration += 1
        now = time.time()

        # ── Echter Scraper-Versuch (nur jede 4. Iteration um Last zu sparen) ──
        real_added = 0
        if iteration % 4 == 1:
            try:
                results = scraper.search(page=1)
                for car_data in results:
                    title_lower = (car_data.get('title') or '').lower()
                    if any(t in title_lower for t in ('suche ', 'gesuch', '[suche]', 'wird gesucht', ' suche ')):
                        continue
                    if _save_and_broadcast(app, car_data):
                        real_added += 1
                if real_added > 0:
                    logger.info(f"[LIVE] {real_added} echte Inserate gefunden")
            except Exception as e:
                logger.debug(f"Scraper-Exception: {e}")

        # ── Demo-Simulation IMMER ALS FALLBACK ──────────────────────
        # Wenn echter Scraper nichts liefert, simulieren wir alle 25s ein Inserat.
        # Erstes Demo-Auto erscheint nach ~5 Sekunden (= sleep_time unten).
        if real_added == 0 and (now - last_sim_time) >= SIM_INTERVAL:
            try:
                from services.demo_data import generate_live_car
                car_data = generate_live_car()
                if _save_and_broadcast(app, car_data):
                    last_sim_time = time.time()
                    scraper_status['last_scrape'] = datetime.utcnow().strftime('%H:%M:%S')
                    logger.info(f"[SIM] Demo-Inserat: {car_data['title']}")
            except Exception as e:
                logger.warning(f"Demo-Simulation Fehler: {e}")

        # Warten bis zum nächsten Zyklus (5 Sekunden — ermöglicht 25s/Demo)
        time.sleep(5)

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
