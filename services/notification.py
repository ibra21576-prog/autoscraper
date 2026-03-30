import logging
from datetime import datetime
from flask_mail import Message
from models import db, SearchAlert

logger = logging.getLogger(__name__)


def create_alert(brand=None, model=None, min_price=None, max_price=None,
                 min_year=None, max_mileage=None, fuel_type=None, email=None):
    """Neuen Such-Alert erstellen."""
    alert = SearchAlert(
        brand=brand, model=model, min_price=min_price, max_price=max_price,
        min_year=min_year, max_mileage=max_mileage, fuel_type=fuel_type,
        email=email, is_active=True
    )
    db.session.add(alert)
    db.session.commit()
    return alert


def get_alerts():
    """Alle Alerts abrufen."""
    return SearchAlert.query.order_by(SearchAlert.created_at.desc()).all()


def toggle_alert(alert_id):
    """Alert aktivieren/deaktivieren."""
    alert = SearchAlert.query.get(alert_id)
    if alert:
        alert.is_active = not alert.is_active
        db.session.commit()
        return True
    return False


def delete_alert(alert_id):
    """Alert löschen."""
    alert = SearchAlert.query.get(alert_id)
    if alert:
        db.session.delete(alert)
        db.session.commit()
        return True
    return False


def check_alerts(mail, app):
    """Alle aktiven Alerts prüfen und Benachrichtigungen senden."""
    from services.search_service import search_cars

    with app.app_context():
        alerts = SearchAlert.query.filter_by(is_active=True).all()

        for alert in alerts:
            try:
                results = search_cars(
                    brand=alert.brand, model=alert.model,
                    price_min=alert.min_price, price_max=alert.max_price,
                    year_min=alert.min_year, mileage_max=alert.max_mileage,
                    fuel_type=alert.fuel_type
                )

                # Nur neue Ergebnisse seit letzter Prüfung
                new_results = []
                if alert.last_checked:
                    new_results = [r for r in results if r.first_seen > alert.last_checked]
                else:
                    new_results = results[:5]  # Beim ersten Mal max 5

                if new_results and alert.email:
                    send_alert_email(mail, alert, new_results)

                alert.last_checked = datetime.utcnow()
                db.session.commit()

            except Exception as e:
                logger.error(f"Alert check failed for {alert.id}: {e}")


def send_alert_email(mail, alert, cars):
    """Alert-Email senden."""
    try:
        search_desc = f"{alert.brand or 'Alle'} {alert.model or ''}"
        if alert.max_price:
            search_desc += f" bis {alert.max_price}€"

        car_list = ""
        for car in cars[:10]:
            price_str = f"{car.price:,.0f}€".replace(',', '.') if car.price else 'k.A.'
            car_list += f"- {car.title} | {price_str} | {car.url}\n"

        msg = Message(
            subject=f"AutoScraper: {len(cars)} neue Ergebnisse für {search_desc}",
            recipients=[alert.email],
            body=f"""Hallo!

Es gibt {len(cars)} neue Ergebnisse für deine Suche: {search_desc}

{car_list}

---
AutoScraper - Dein Auto-Preisvergleich
"""
        )
        mail.send(msg)
        logger.info(f"Alert email sent to {alert.email}")
    except Exception as e:
        logger.error(f"Failed to send alert email: {e}")
