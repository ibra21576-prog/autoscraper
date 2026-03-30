import logging
from datetime import datetime
from models import db, Car, PriceHistory

logger = logging.getLogger(__name__)


def track_car(car_id):
    """Fahrzeug zum Tracking hinzufügen."""
    car = Car.query.get(car_id)
    if car:
        car.is_tracked = True
        db.session.commit()
        return True
    return False


def untrack_car(car_id):
    """Fahrzeug vom Tracking entfernen."""
    car = Car.query.get(car_id)
    if car:
        car.is_tracked = False
        db.session.commit()
        return True
    return False


def get_tracked_cars():
    """Alle getrackten Fahrzeuge abrufen."""
    cars = Car.query.filter_by(is_tracked=True).order_by(Car.last_seen.desc()).all()
    result = []
    for car in cars:
        car_dict = car.to_dict()
        history = PriceHistory.query.filter_by(car_id=car.id).order_by(PriceHistory.recorded_at).all()
        car_dict['price_history'] = [
            {'price': h.price, 'date': h.recorded_at.strftime('%d.%m.%Y %H:%M')}
            for h in history
        ]
        if len(history) >= 2:
            car_dict['price_change'] = history[-1].price - history[-2].price
        else:
            car_dict['price_change'] = 0
        result.append(car_dict)
    return result


def get_car_detail(car_id):
    """Fahrzeug-Details mit Preishistorie abrufen."""
    car = Car.query.get(car_id)
    if not car:
        return None
    car_dict = car.to_dict()
    history = PriceHistory.query.filter_by(car_id=car.id).order_by(PriceHistory.recorded_at).all()
    car_dict['price_history'] = [
        {'price': h.price, 'date': h.recorded_at.strftime('%d.%m.%Y %H:%M')}
        for h in history
    ]
    return car_dict
