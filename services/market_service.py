"""
Marktanalyse-Service: aggregiert Preishistorie nach Tag
und berechnet min/avg/max-Preise sowie Gesamtmarkt-Übersichten.
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy import func
from models import db, Car, PriceHistory

logger = logging.getLogger(__name__)

# Preissegmente
SEGMENTS = [
    ('Budget',   0,      10000),
    ('Mittel',   10000,  30000),
    ('Premium',  30000,  80000),
    ('Luxus',    80000,  10_000_000),
]


def get_market_data(brand=None, model=None, fuel_type=None, days=90):
    """
    Tages-Datenpunkte: min/avg/max-Preis pro Tag aus PriceHistory.
    Gibt eine leere Liste zurück wenn keine Daten vorhanden.
    """
    since = datetime.utcnow() - timedelta(days=days)

    query = (
        db.session.query(
            func.date(PriceHistory.recorded_at).label('date'),
            func.min(PriceHistory.price).label('min_price'),
            func.avg(PriceHistory.price).label('avg_price'),
            func.max(PriceHistory.price).label('max_price'),
            func.count(func.distinct(Car.id)).label('count'),
        )
        .join(Car, Car.id == PriceHistory.car_id)
        .filter(PriceHistory.recorded_at >= since)
        .filter(PriceHistory.price > 0)
        .filter(PriceHistory.price < 10_000_000)   # Ausreißer filtern
    )

    if brand:
        query = query.filter(Car.brand.ilike(f'%{brand}%'))
    if model:
        query = query.filter(Car.model.ilike(f'%{model}%'))
    if fuel_type:
        query = query.filter(Car.fuel_type.ilike(f'%{fuel_type}%'))

    rows = (
        query
        .group_by(func.date(PriceHistory.recorded_at))
        .order_by(func.date(PriceHistory.recorded_at))
        .all()
    )

    return [
        {
            'date': str(row.date),
            'min_price': int(row.min_price),
            'avg_price': int(row.avg_price),
            'max_price': int(row.max_price),
            'count': int(row.count),
        }
        for row in rows
    ]


def get_market_stats(brand=None, model=None, fuel_type=None, days=90):
    """Zusammenfassende Statistiken für den gefilterten Markt."""
    data = get_market_data(brand=brand, model=model, fuel_type=fuel_type, days=days)
    if not data:
        return None

    all_avg = [d['avg_price'] for d in data]
    all_min = [d['min_price'] for d in data]
    all_max = [d['max_price'] for d in data]
    all_count = [d['count'] for d in data]

    # Trend: erste Hälfte vs. zweite Hälfte
    mid = len(all_avg) // 2
    if mid > 0:
        early_avg = sum(all_avg[:mid]) / mid
        late_avg = sum(all_avg[mid:]) / max(len(all_avg[mid:]), 1)
        trend_pct = ((late_avg - early_avg) / early_avg * 100) if early_avg else 0
    else:
        trend_pct = 0

    # Günstigste aktuelle Listings
    since_30 = datetime.utcnow() - timedelta(days=30)
    q = Car.query.filter(Car.price > 0, Car.price < 10_000_000, Car.last_seen >= since_30)
    if brand:
        q = q.filter(Car.brand.ilike(f'%{brand}%'))
    if model:
        q = q.filter(Car.model.ilike(f'%{model}%'))
    if fuel_type:
        q = q.filter(Car.fuel_type.ilike(f'%{fuel_type}%'))

    cheapest = q.order_by(Car.price.asc()).limit(3).all()

    return {
        'total_days': len(data),
        'total_listings': sum(all_count),
        'current_avg': all_avg[-1] if all_avg else 0,
        'current_min': all_min[-1] if all_min else 0,
        'current_max': all_max[-1] if all_max else 0,
        'overall_min': min(all_min),
        'overall_max': max(all_max),
        'trend_pct': round(trend_pct, 1),
        'cheapest': cheapest,
    }


def get_full_market_overview(days=90):
    """
    Gesamtmarkt-Übersicht ohne Marken-/Modellfilter:
    - Gesamtstatistiken
    - Top-Marken nach Anzahl
    - Kraftstoffverteilung
    - Preissegmente
    - Plattform-Aufteilung
    - Tages-Chart (wie get_market_data, aber ungefiltert)
    """
    since = datetime.utcnow() - timedelta(days=days)

    # -- Gesamtanzahl & Durchschnittspreise --
    total_q = db.session.query(
        func.count(Car.id).label('cnt'),
        func.avg(Car.price).label('avg'),
        func.min(Car.price).label('min'),
        func.max(Car.price).label('max'),
    ).filter(Car.price > 0, Car.price < 10_000_000, Car.last_seen >= since)
    total = total_q.one()

    # -- Top-Marken (nach Listinganzahl) --
    brand_rows = (
        db.session.query(
            Car.brand,
            func.count(Car.id).label('cnt'),
            func.avg(Car.price).label('avg_price'),
        )
        .filter(Car.price > 0, Car.price < 10_000_000, Car.last_seen >= since)
        .filter(Car.brand.isnot(None), Car.brand != '')
        .group_by(Car.brand)
        .order_by(func.count(Car.id).desc())
        .limit(12)
        .all()
    )

    top_brands = [
        {
            'brand': row.brand,
            'count': int(row.cnt),
            'avg_price': int(row.avg_price or 0),
        }
        for row in brand_rows
    ]

    # -- Kraftstoffverteilung --
    fuel_rows = (
        db.session.query(
            Car.fuel_type,
            func.count(Car.id).label('cnt'),
        )
        .filter(Car.last_seen >= since)
        .filter(Car.fuel_type.isnot(None), Car.fuel_type != '')
        .group_by(Car.fuel_type)
        .order_by(func.count(Car.id).desc())
        .limit(8)
        .all()
    )
    fuel_distribution = [
        {'fuel': row.fuel_type, 'count': int(row.cnt)}
        for row in fuel_rows
    ]

    # -- Preissegmente --
    segment_data = []
    for label, low, high in SEGMENTS:
        cnt = Car.query.filter(
            Car.price >= low,
            Car.price < high,
            Car.last_seen >= since,
        ).count()
        segment_data.append({'segment': label, 'count': cnt})

    # -- Plattform-Aufteilung --
    platform_rows = (
        db.session.query(
            Car.platform,
            func.count(Car.id).label('cnt'),
        )
        .filter(Car.last_seen >= since)
        .group_by(Car.platform)
        .order_by(func.count(Car.id).desc())
        .all()
    )
    platform_distribution = [
        {'platform': row.platform, 'count': int(row.cnt)}
        for row in platform_rows
    ]

    # -- Tages-Chart (ungefiltert) --
    daily_rows = (
        db.session.query(
            func.date(PriceHistory.recorded_at).label('date'),
            func.min(PriceHistory.price).label('min_price'),
            func.avg(PriceHistory.price).label('avg_price'),
            func.max(PriceHistory.price).label('max_price'),
            func.count(func.distinct(Car.id)).label('count'),
        )
        .join(Car, Car.id == PriceHistory.car_id)
        .filter(PriceHistory.recorded_at >= since)
        .filter(PriceHistory.price > 0, PriceHistory.price < 10_000_000)
        .group_by(func.date(PriceHistory.recorded_at))
        .order_by(func.date(PriceHistory.recorded_at))
        .all()
    )
    daily_data = [
        {
            'date': str(row.date),
            'min_price': int(row.min_price),
            'avg_price': int(row.avg_price),
            'max_price': int(row.max_price),
            'count': int(row.count),
        }
        for row in daily_rows
    ]

    return {
        'total_count': int(total.cnt or 0),
        'avg_price': int(total.avg or 0),
        'min_price': int(total.min or 0),
        'max_price': int(total.max or 0),
        'top_brands': top_brands,
        'fuel_distribution': fuel_distribution,
        'segment_data': segment_data,
        'platform_distribution': platform_distribution,
        'daily_data': daily_data,
        'days': days,
    }
