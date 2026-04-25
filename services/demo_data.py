"""
Demo-Daten für den Live Feed wenn keine echten Scraper-Daten verfügbar sind.
Enthält realistische deutsche Kfz-Inserate mit Bildern von Unsplash.
"""
import random
import hashlib
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Unsplash car photo IDs (specific IDs known to be cars)
_CAR_IMAGES = [
    "https://images.unsplash.com/photo-1555215695-3004980ad54e?w=600&q=80",  # BMW M5
    "https://images.unsplash.com/photo-1503376780353-7e6692767b70?w=600&q=80",  # Porsche 911
    "https://images.unsplash.com/photo-1618843479313-40f8afb4b4d8?w=600&q=80",  # Mercedes
    "https://images.unsplash.com/photo-1606664515524-ed2f786a0bd6?w=600&q=80",  # Audi
    "https://images.unsplash.com/photo-1494976388531-d1058494cdd8?w=600&q=80",  # Generic car
    "https://images.unsplash.com/photo-1580274455191-1c62238fa333?w=600&q=80",  # BMW
    "https://images.unsplash.com/photo-1549399542-7e8f2e928464?w=600&q=80",  # Car interior
    "https://images.unsplash.com/photo-1542362567-b07e54358753?w=600&q=80",  # Sports car
    "https://images.unsplash.com/photo-1552519507-da3b142c6e3d?w=600&q=80",  # Yellow sports car
    "https://images.unsplash.com/photo-1525609004556-c46c7d6cf023?w=600&q=80",  # Blue car
    "https://images.unsplash.com/photo-1536700503339-1e4b06520771?w=600&q=80",  # Red car
    "https://images.unsplash.com/photo-1511919884226-fd3cad34687c?w=600&q=80",  # Car
    "https://images.unsplash.com/photo-1609521263047-f8f205293f24?w=600&q=80",  # VW
    "https://images.unsplash.com/photo-1616455579100-2ceaa4ec2d52?w=600&q=80",  # BMW 3er
    "https://images.unsplash.com/photo-1544636331-e26879cd4d9b?w=600&q=80",  # White BMW
    "https://images.unsplash.com/photo-1502877338535-766e1452684a?w=600&q=80",  # Sedan
    "https://images.unsplash.com/photo-1486262715619-67b85e0b08d3?w=600&q=80",  # Old car
    "https://images.unsplash.com/photo-1563720223185-11003d516935?w=600&q=80",  # SUV
    "https://images.unsplash.com/photo-1600712242805-5f78671b24da?w=600&q=80",  # White car
    "https://images.unsplash.com/photo-1567818735868-e71b99932e29?w=600&q=80",  # Luxury car
]

_CITIES = [
    "Berlin", "Hamburg", "München", "Köln", "Frankfurt am Main",
    "Stuttgart", "Düsseldorf", "Dortmund", "Essen", "Leipzig",
    "Bremen", "Dresden", "Hannover", "Nürnberg", "Duisburg",
    "Bochum", "Wuppertal", "Bielefeld", "Bonn", "Münster",
    "Karlsruhe", "Mannheim", "Augsburg", "Wiesbaden", "Gelsenkirchen",
    "Mönchengladbach", "Braunschweig", "Kiel", "Chemnitz", "Aachen",
    "Halle", "Magdeburg", "Freiburg", "Krefeld", "Lübeck",
    "Oberhausen", "Erfurt", "Mainz", "Rostock", "Kassel",
]

_SELLER_TYPES = ["Privat", "Privat", "Privat", "Händler", "Händler"]

_FUEL_TYPES = ["Benzin", "Benzin", "Diesel", "Diesel", "Diesel", "Hybrid", "Elektro", "Benzin"]

_TRANSMISSIONS = ["Schaltgetriebe", "Schaltgetriebe", "Automatik", "Automatik", "Schaltgetriebe"]

_COLORS = [
    "Schwarz", "Weiß", "Silber", "Grau", "Blau", "Rot", "Grün", "Braun",
    "Beige", "Orange", "Gold", "Violett",
]

# (brand, model, base_price_min, base_price_max, typical_years)
_CAR_SPECS = [
    # Volkswagen
    ("Volkswagen", "Golf", 6000, 32000, range(2008, 2024)),
    ("Volkswagen", "Golf GTI", 15000, 45000, range(2012, 2024)),
    ("Volkswagen", "Polo", 4000, 22000, range(2008, 2024)),
    ("Volkswagen", "Passat", 7000, 38000, range(2008, 2024)),
    ("Volkswagen", "Tiguan", 12000, 45000, range(2010, 2024)),
    ("Volkswagen", "T-Roc", 15000, 38000, range(2018, 2024)),
    ("Volkswagen", "ID.4", 25000, 52000, range(2021, 2024)),
    # BMW
    ("BMW", "3er", 10000, 55000, range(2008, 2024)),
    ("BMW", "5er", 14000, 70000, range(2008, 2024)),
    ("BMW", "1er", 7000, 38000, range(2008, 2024)),
    ("BMW", "X3", 18000, 60000, range(2010, 2024)),
    ("BMW", "X5", 25000, 90000, range(2010, 2024)),
    ("BMW", "M3", 40000, 120000, range(2015, 2024)),
    ("BMW", "2er", 12000, 45000, range(2014, 2024)),
    # Mercedes-Benz
    ("Mercedes-Benz", "C-Klasse", 12000, 65000, range(2010, 2024)),
    ("Mercedes-Benz", "E-Klasse", 16000, 80000, range(2010, 2024)),
    ("Mercedes-Benz", "A-Klasse", 10000, 42000, range(2012, 2024)),
    ("Mercedes-Benz", "GLC", 22000, 75000, range(2015, 2024)),
    ("Mercedes-Benz", "GLE", 35000, 100000, range(2015, 2024)),
    ("Mercedes-Benz", "CLA", 16000, 52000, range(2013, 2024)),
    # Audi
    ("Audi", "A3", 9000, 42000, range(2010, 2024)),
    ("Audi", "A4", 11000, 55000, range(2010, 2024)),
    ("Audi", "A6", 14000, 70000, range(2010, 2024)),
    ("Audi", "Q3", 15000, 48000, range(2012, 2024)),
    ("Audi", "Q5", 20000, 65000, range(2012, 2024)),
    ("Audi", "RS3", 35000, 75000, range(2017, 2024)),
    # Opel
    ("Opel", "Corsa", 3000, 22000, range(2005, 2024)),
    ("Opel", "Astra", 4000, 25000, range(2005, 2024)),
    ("Opel", "Mokka", 8000, 32000, range(2012, 2024)),
    ("Opel", "Insignia", 6000, 28000, range(2009, 2024)),
    # Ford
    ("Ford", "Focus", 4000, 24000, range(2005, 2024)),
    ("Ford", "Fiesta", 3000, 20000, range(2005, 2024)),
    ("Ford", "Kuga", 9000, 35000, range(2010, 2024)),
    ("Ford", "Mustang", 30000, 90000, range(2015, 2024)),
    # Toyota
    ("Toyota", "Yaris", 4000, 22000, range(2006, 2024)),
    ("Toyota", "Corolla", 6000, 30000, range(2008, 2024)),
    ("Toyota", "RAV4", 12000, 48000, range(2010, 2024)),
    ("Toyota", "C-HR", 14000, 35000, range(2017, 2024)),
    # Skoda
    ("Skoda", "Octavia", 6000, 32000, range(2008, 2024)),
    ("Skoda", "Fabia", 3500, 20000, range(2006, 2024)),
    ("Skoda", "Kodiaq", 15000, 42000, range(2017, 2024)),
    ("Skoda", "Superb", 9000, 38000, range(2010, 2024)),
    # Seat
    ("Seat", "Ibiza", 3000, 20000, range(2006, 2024)),
    ("Seat", "Leon", 5000, 28000, range(2006, 2024)),
    ("Seat", "Ateca", 12000, 35000, range(2016, 2024)),
    # Porsche
    ("Porsche", "911", 60000, 250000, range(2010, 2024)),
    ("Porsche", "Cayenne", 35000, 130000, range(2010, 2024)),
    ("Porsche", "Macan", 30000, 90000, range(2014, 2024)),
    # Renault
    ("Renault", "Clio", 3000, 20000, range(2005, 2024)),
    ("Renault", "Megane", 4000, 24000, range(2005, 2024)),
    ("Renault", "Captur", 8000, 28000, range(2013, 2024)),
    # Hyundai
    ("Hyundai", "i30", 5000, 26000, range(2008, 2024)),
    ("Hyundai", "Tucson", 10000, 38000, range(2010, 2024)),
    ("Hyundai", "Kona", 10000, 32000, range(2017, 2024)),
    # Kia
    ("Kia", "Ceed", 5000, 26000, range(2008, 2024)),
    ("Kia", "Sportage", 10000, 38000, range(2010, 2024)),
    ("Kia", "Stinger", 22000, 55000, range(2018, 2024)),
    # Volvo
    ("Volvo", "V40", 8000, 30000, range(2012, 2024)),
    ("Volvo", "XC60", 20000, 65000, range(2010, 2024)),
    ("Volvo", "V90", 25000, 70000, range(2016, 2024)),
    # Tesla
    ("Tesla", "Model 3", 28000, 65000, range(2019, 2024)),
    ("Tesla", "Model Y", 35000, 72000, range(2021, 2024)),
    ("Tesla", "Model S", 50000, 120000, range(2015, 2024)),
    # Mini
    ("MINI", "Cooper", 8000, 32000, range(2010, 2024)),
    ("MINI", "Countryman", 12000, 42000, range(2011, 2024)),
    # Mazda
    ("Mazda", "CX-5", 12000, 38000, range(2012, 2024)),
    ("Mazda", "3", 7000, 28000, range(2010, 2024)),
    ("Mazda", "MX-5", 15000, 40000, range(2008, 2024)),
]

_CONDITION_PHRASES = [
    "Top Zustand", "Gepflegt", "Scheckheftgepflegt", "TÜV neu",
    "Unfallfrei", "Nichtraucherfahrzeug", "1. Hand", "2. Hand",
    "Gebraucht", "Sehr guter Zustand",
]

_POWER_VALUES = [75, 85, 95, 102, 110, 116, 120, 125, 130, 140, 150, 163, 170, 184, 190, 200, 218, 230, 245, 258, 272, 285, 300, 320, 340, 360, 390, 430, 450, 510]


def _make_title(brand, model, year, condition):
    extras = random.choice(["", "", " Navi", " Xenon", " PDC", " SHZ", " Klimaautomatik", " Leder"])
    return f"{brand} {model} {year} {condition}{extras}".strip()


def _make_external_id(title, price, year, city):
    raw = f"demo_{title}_{price}_{year}_{city}"
    return "demo_" + hashlib.md5(raw.encode()).hexdigest()[:12]


def generate_demo_cars(count=100):
    """Erstellt eine Liste realistischer Kfz-Inserate als Demo-Daten."""
    rng = random.Random(42)  # fixed seed for reproducibility
    cars = []

    specs_pool = _CAR_SPECS * (count // len(_CAR_SPECS) + 2)
    rng.shuffle(specs_pool)

    for i in range(count):
        brand, model, price_min, price_max, years = specs_pool[i]
        year = rng.choice(list(years))
        # Price decreases with age
        age = 2025 - year
        price = int(rng.uniform(price_min, price_max) * max(0.3, 1 - age * 0.04))
        price = max(price_min * 0.3, price)
        price = round(price / 100) * 100  # round to nearest 100

        # Mileage correlates with age
        mileage = int(rng.gauss(age * 14000, age * 4000))
        mileage = max(0, min(400000, mileage))
        mileage = round(mileage / 1000) * 1000

        fuel = rng.choice(_FUEL_TYPES)
        if year >= 2022 and rng.random() < 0.3:
            fuel = "Elektro"
        if year < 2010:
            fuel = rng.choice(["Benzin", "Diesel"])

        transmission = rng.choice(_TRANSMISSIONS)
        color = rng.choice(_COLORS)
        power = rng.choice(_POWER_VALUES)
        city = rng.choice(_CITIES)
        seller_type = rng.choice(_SELLER_TYPES)
        condition = rng.choice(_CONDITION_PHRASES)
        image_url = rng.choice(_CAR_IMAGES)

        title = _make_title(brand, model, year, condition)
        external_id = _make_external_id(title, price, year, city)

        # Fake timestamp — spread over last 48 hours
        hours_ago = rng.uniform(0, 48)
        first_seen = datetime.utcnow() - timedelta(hours=hours_ago)

        cars.append({
            "platform": "kleinanzeigen",
            "external_id": external_id,
            "title": title,
            "brand": brand,
            "model": model,
            "price": int(price),
            "mileage": int(mileage),
            "year": year,
            "fuel_type": fuel,
            "power": f"{power} PS",
            "transmission": transmission,
            "color": color,
            "seller_type": seller_type,
            "location": city,
            "image_url": image_url,
            "url": "",
            "first_seen": first_seen,
            "last_seen": first_seen,
        })

    # Sort by first_seen descending (newest first)
    cars.sort(key=lambda c: c["first_seen"], reverse=True)
    return cars


def generate_live_car():
    """
    Erzeugt ein einzelnes, einzigartiges Demo-Inserat für den Live-Feed.
    Jeder Aufruf liefert ein anderes Auto (zeitbasierter Seed).
    """
    import time as _time
    rng = random.Random(_time.time())

    brand, model, price_min, price_max, years = rng.choice(_CAR_SPECS)
    year = rng.choice(list(years))
    age = 2025 - year
    price = int(rng.uniform(price_min, price_max) * max(0.3, 1 - age * 0.04))
    price = max(int(price_min * 0.3), price)
    price = round(price / 100) * 100

    mileage = int(rng.gauss(age * 14000, age * 4000))
    mileage = max(0, min(400000, mileage))
    mileage = round(mileage / 1000) * 1000

    fuel = rng.choice(_FUEL_TYPES)
    if year >= 2022 and rng.random() < 0.3:
        fuel = "Elektro"
    if year < 2010:
        fuel = rng.choice(["Benzin", "Diesel"])

    color       = rng.choice(_COLORS)
    power       = rng.choice(_POWER_VALUES)
    city        = rng.choice(_CITIES)
    seller_type = rng.choice(_SELLER_TYPES)
    transmission= rng.choice(_TRANSMISSIONS)
    condition   = rng.choice(_CONDITION_PHRASES)
    image_url   = rng.choice(_CAR_IMAGES)

    title = _make_title(brand, model, year, condition)

    # Unique ID basierend auf Zeitstempel + Zufall
    import time as _time2
    uid = hashlib.md5(f"live_{_time2.time()}_{rng.random()}".encode()).hexdigest()[:12]
    external_id = f"live_{uid}"

    return {
        "platform": "kleinanzeigen",
        "external_id": external_id,
        "title": title,
        "brand": brand,
        "model": model,
        "price": int(price),
        "mileage": int(mileage),
        "year": year,
        "fuel_type": fuel,
        "power": f"{power} PS",
        "transmission": transmission,
        "color": color,
        "seller_type": seller_type,
        "location": city,
        "image_url": image_url,
        "url": "",
        "first_seen": datetime.utcnow(),
        "last_seen": datetime.utcnow(),
    }


def seed_demo_data(app, count=100, force=False):
    """
    Befüllt die DB mit Demo-Daten wenn sie leer ist.
    force=True überschreibt auch vorhandene Demo-Daten.
    Gibt zurück: (stored, skipped)
    """
    from models import db, Car, PriceHistory

    with app.app_context():
        existing_count = Car.query.count()
        if existing_count > 0 and not force:
            logger.info(f"[DEMO] DB hat bereits {existing_count} Einträge — Demo-Seed übersprungen")
            return 0, existing_count

        cars_data = generate_demo_cars(count)
        stored = 0

        for data in cars_data:
            try:
                existing = Car.query.filter_by(
                    platform=data["platform"],
                    external_id=data["external_id"]
                ).first()
                if existing and not force:
                    continue

                if existing:
                    car = existing
                    car.price = data["price"]
                    car.last_seen = datetime.utcnow()
                else:
                    car = Car(
                        platform=data["platform"],
                        external_id=data["external_id"],
                        title=data["title"],
                        brand=data["brand"],
                        model=data["model"],
                        price=data["price"],
                        mileage=data["mileage"],
                        year=data["year"],
                        fuel_type=data["fuel_type"],
                        power=data["power"],
                        transmission=data["transmission"],
                        color=data["color"],
                        seller_type=data["seller_type"],
                        location=data["location"],
                        url=data["url"],
                        image_url=data["image_url"],
                        first_seen=data["first_seen"],
                        last_seen=data["last_seen"],
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
                logger.debug(f"[DEMO] Fehler beim Speichern: {e}")

        logger.info(f"[DEMO] {stored} Demo-Fahrzeuge gespeichert")
        return stored, existing_count
