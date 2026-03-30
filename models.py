from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Car(db.Model):
    __tablename__ = 'cars'

    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(50), nullable=False)
    external_id = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(500))
    brand = db.Column(db.String(100))
    model = db.Column(db.String(100))
    price = db.Column(db.Integer)
    mileage = db.Column(db.Integer)
    year = db.Column(db.Integer)
    fuel_type = db.Column(db.String(50))
    power = db.Column(db.String(50))
    transmission = db.Column(db.String(50))
    color = db.Column(db.String(50))
    description = db.Column(db.Text)
    seller_name = db.Column(db.String(200))
    seller_type = db.Column(db.String(50))  # 'Privat' / 'Händler'
    location = db.Column(db.String(200))
    url = db.Column(db.String(1000))
    image_url = db.Column(db.String(1000))  # Hauptbild
    is_tracked = db.Column(db.Boolean, default=False)
    first_seen = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

    price_history = db.relationship('PriceHistory', backref='car', lazy=True, cascade='all, delete-orphan')
    images = db.relationship('CarImage', backref='car', lazy=True, cascade='all, delete-orphan',
                             order_by='CarImage.position')

    __table_args__ = (db.UniqueConstraint('platform', 'external_id', name='uq_platform_external_id'),)

    def to_dict(self):
        return {
            'id': self.id,
            'platform': self.platform,
            'title': self.title,
            'brand': self.brand,
            'model': self.model,
            'price': self.price,
            'mileage': self.mileage,
            'year': self.year,
            'fuel_type': self.fuel_type,
            'power': self.power,
            'transmission': self.transmission,
            'color': self.color,
            'description': self.description,
            'seller_name': self.seller_name,
            'seller_type': self.seller_type,
            'location': self.location,
            'url': self.url,
            'image_url': self.image_url,
            'images': [img.image_url for img in self.images] if self.images else [],
            'is_tracked': self.is_tracked,
            'first_seen': self.first_seen.strftime('%d.%m.%Y %H:%M') if self.first_seen else '',
        }


class CarImage(db.Model):
    __tablename__ = 'car_images'

    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey('cars.id'), nullable=False)
    image_url = db.Column(db.String(1000), nullable=False)
    position = db.Column(db.Integer, default=0)


class PriceHistory(db.Model):
    __tablename__ = 'price_history'

    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey('cars.id'), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)


class SearchAlert(db.Model):
    __tablename__ = 'search_alerts'

    id = db.Column(db.Integer, primary_key=True)
    brand = db.Column(db.String(100))
    model = db.Column(db.String(100))
    min_price = db.Column(db.Integer)
    max_price = db.Column(db.Integer)
    min_year = db.Column(db.Integer)
    max_mileage = db.Column(db.Integer)
    fuel_type = db.Column(db.String(50))
    email = db.Column(db.String(200), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_checked = db.Column(db.DateTime)
