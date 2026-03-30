"""
Background-Scraper: Sammelt Daten von AutoScout24 und Kleinanzeigen
im Hintergrund per Cronjob (alle 1-2 Stunden).
Speichert Ergebnisse in der Datenbank mit Deduplizierung.
"""

import hashlib
import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

# Status-Tracking
bg_status = {
    'running': False,
    'last_run': None,
    'last_results': {'autoscout24': 0, 'kleinanzeigen': 0},
    'total_stored': 0,
    'errors': [],
}


def _generate_external_id(item, platform):
    """Generiert eine stabile external_id aus Titel + Preis + Plattform."""
    raw = f"{platform}_{item.get('title', '')}_{item.get('price', '')}_{item.get('km', '')}_{item.get('year', '')}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _store_results(results, brand, model, app):
    """Speichert Scraper-Ergebnisse in der Datenbank mit Deduplizierung."""
    from models import db, Car, PriceHistory

    stored = 0
    updated = 0

    with app.app_context():
        for item in results:
            try:
                platform_map = {
                    'AutoScout24': 'autoscout24',
                    'Kleinanzeigen': 'kleinanzeigen',
                    'mobile.de': 'mobile_de',
                }
                platform = platform_map.get(item.get('source'), item.get('source', 'unknown'))
                ext_id = _generate_external_id(item, platform)

                existing = Car.query.filter_by(
                    platform=platform,
                    external_id=ext_id
                ).first()

                if existing:
                    # Preis-Update
                    old_price = existing.price
                    new_price = item.get('price')
                    existing.last_seen = datetime.utcnow()

                    if new_price and old_price != new_price:
                        existing.price = new_price
                        ph = PriceHistory(car_id=existing.id, price=new_price)
                        db.session.add(ph)
                        updated += 1

                    db.session.commit()
                else:
                    car = Car(
                        platform=platform,
                        external_id=ext_id,
                        title=item.get('title', 'Unbekannt'),
                        brand=brand,
                        model=model or None,
                        price=item.get('price'),
                        mileage=item.get('km'),
                        year=item.get('year'),
                        url='',
                        first_seen=datetime.utcnow(),
                        last_seen=datetime.utcnow(),
                    )
                    db.session.add(car)
                    db.session.flush()

                    if car.price:
                        ph = PriceHistory(car_id=car.id, price=car.price)
                        db.session.add(ph)

                    db.session.commit()
                    stored += 1

            except Exception as e:
                db.session.rollback()
                logger.debug(f"Fehler beim Speichern: {e}")

    return stored, updated


def run_background_scrape(app, brands=None):
    """
    Führt einen kompletten Background-Scrape durch.
    Scrapt die Top-Marken von AutoScout24 und Kleinanzeigen.
    """
    from services.playwright_scraper import run_live_search, CAR_DATA

    bg_status['running'] = True
    bg_status['errors'] = []

    # Standard: Top 10 beliebteste Marken
    if not brands:
        brands = ['BMW', 'Mercedes-Benz', 'Audi', 'Volkswagen', 'Opel',
                  'Ford', 'Toyota', 'Hyundai', 'Skoda', 'Renault']

    total_stored = 0
    total_as = 0
    total_ka = 0

    for brand in brands:
        try:
            logger.info(f"[BG] Scrape: {brand}")
            # Nur AutoScout24 und Kleinanzeigen (mobile.de ist instabil)
            results, _ = run_live_search(
                brand=brand,
                sources=['autoscout24', 'kleinanzeigen']
            )

            if results:
                stored, updated = _store_results(results, brand, None, app)
                total_stored += stored
                # Zähle nach Quelle
                for r in results:
                    if r.get('source') == 'AutoScout24':
                        total_as += 1
                    elif r.get('source') == 'Kleinanzeigen':
                        total_ka += 1

                logger.info(f"[BG] {brand}: {len(results)} gefunden, {stored} neu, {updated} aktualisiert")

        except Exception as e:
            error_msg = f"{brand}: {str(e)[:100]}"
            bg_status['errors'].append(error_msg)
            logger.error(f"[BG] Fehler bei {brand}: {e}")

    bg_status['running'] = False
    bg_status['last_run'] = datetime.utcnow().strftime('%d.%m.%Y %H:%M')
    bg_status['last_results'] = {'autoscout24': total_as, 'kleinanzeigen': total_ka}
    bg_status['total_stored'] += total_stored

    logger.info(f"[BG] Fertig: {total_stored} neue Einträge gespeichert")
    return total_stored


def start_background_scheduler(app, scheduler):
    """Registriert den Background-Scraper als APScheduler-Job (alle 2 Stunden)."""

    def _job():
        # In eigenem Thread ausführen damit der Scheduler nicht blockiert
        thread = threading.Thread(
            target=run_background_scrape,
            args=(app,),
            daemon=True
        )
        thread.start()

    scheduler.add_job(
        func=_job,
        trigger='interval',
        hours=2,
        id='background_scraper',
        replace_existing=True,
        next_run_time=None,  # Nicht sofort starten
    )
    logger.info("[BG] Background-Scraper registriert (alle 2 Stunden)")


def get_bg_status():
    return dict(bg_status)
