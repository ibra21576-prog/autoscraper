import json
import os
import time
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, session
from flask_mail import Mail
from apscheduler.schedulers.background import BackgroundScheduler

# .env laden (lokal: DATABASE_URL -> Neon PostgreSQL)
from dotenv import load_dotenv
load_dotenv()

from config import Config
from models import db, Car, User

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Flask App
app = Flask(__name__)
app.config.from_object(Config)

# Instance-Ordner sicherstellen (für SQLite DB)
os.makedirs(os.path.join(os.path.dirname(__file__), 'instance'), exist_ok=True)

# Extensions
db.init_app(app)
mail = Mail(app)

# DB erstellen (bestehende Tabellen bleiben erhalten)
with app.app_context():
    db.create_all()


def _cleanup_brands_bg():
    """Brand-Normalisierung im Hintergrund — blockiert nicht den Start."""
    import threading, time
    def _run():
        time.sleep(5)  # kurz warten bis App bereit
        with app.app_context():
            try:
                from scrapers.base import normalize_brand, BaseScraper
                # 1) Normalisiere bekannte aber falsch geschriebene Brands
                dirty = Car.query.filter(Car.brand.isnot(None)).all()
                changed = 0
                for car in dirty:
                    raw = (car.brand or '').strip()
                    if not raw:
                        car.brand = None
                        changed += 1
                        continue
                    norm = normalize_brand(raw)
                    if norm != raw:
                        car.brand = norm
                        changed += 1
                if changed:
                    db.session.commit()
                    logger.info(f"Brand-Normalisierung: {changed} Einträge")
                # 2) Brand aus Titel rekonstruieren wo brand=NULL
                _bs = BaseScraper.__new__(BaseScraper)
                null_cars = Car.query.filter(Car.brand.is_(None), Car.title.isnot(None)).all()
                fixed = 0
                for car in null_cars:
                    b, m = _bs._extract_brand_model(car.title or '')
                    if b:
                        car.brand = b
                        if not car.model and m:
                            car.model = m
                        fixed += 1
                if fixed:
                    db.session.commit()
                    logger.info(f"Brand aus Titel: {fixed} Einträge")
            except Exception as e:
                logger.warning(f"Brand-Bereinigung Fehler: {e}")
    threading.Thread(target=_run, daemon=True).start()

_cleanup_brands_bg()


# --- AUTH CONTEXT PROCESSOR ---

@app.context_processor
def inject_user():
    """Macht current_user in allen Templates verfügbar."""
    user_id = session.get('user_id')
    current_user = None
    if user_id:
        current_user = User.query.get(user_id)
    return dict(current_user=current_user)


# --- AUTH ROUTEN ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if session.get('user_id'):
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')

        if not username or not email or not password:
            flash('Bitte alle Felder ausfüllen.', 'error')
            return render_template('register.html')
        if len(password) < 6:
            flash('Passwort muss mindestens 6 Zeichen lang sein.', 'error')
            return render_template('register.html')
        if password != password2:
            flash('Passwörter stimmen nicht überein.', 'error')
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash('Diese E-Mail-Adresse ist bereits registriert.', 'error')
            return render_template('register.html')
        if User.query.filter_by(username=username).first():
            flash('Dieser Benutzername ist bereits vergeben.', 'error')
            return render_template('register.html')

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        session['user_id'] = user.id
        flash(f'Willkommen, {user.username}!', 'success')
        return redirect(url_for('index'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            flash(f'Willkommen zurück, {user.username}!', 'success')
            next_url = request.args.get('next') or url_for('index')
            return redirect(next_url)
        else:
            flash('E-Mail oder Passwort ist falsch.', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Du wurdest abgemeldet.', 'info')
    return redirect(url_for('index'))


# --- ROUTEN ---

@app.route('/')
def index():
    """Startseite mit Suchformular."""
    from services.playwright_scraper import CAR_DATA
    return render_template('index.html',
                           car_data=CAR_DATA,
                           car_brands=sorted(CAR_DATA.keys()))


@app.route('/live')
def live_feed():
    """Live-Feed - neue Autos in Echtzeit, mit optionalem Marke/Modell-Filter."""
    from services.live_scraper import get_scraper_status
    from sqlalchemy import func
    from services.playwright_scraper import CAR_DATA
    status = get_scraper_status()

    brand = request.args.get('brand', '').strip()
    model = request.args.get('model', '').strip()
    price_min = request.args.get('price_min', type=int)
    price_max = request.args.get('price_max', type=int)
    year_min = request.args.get('year_min', type=int)
    mileage_max = request.args.get('mileage_max', type=int)
    fuel_type = request.args.get('fuel_type', '').strip()
    platform = request.args.get('platform', '').strip()
    sort = request.args.get('sort', 'newest')

    from scrapers.base import normalize_brand, BRAND_NORMALIZE
    from sqlalchemy import or_, and_

    query = Car.query
    if brand:
        canonical = normalize_brand(brand)
        # Alle bekannten Schreibweisen dieser Marke (VW, Volkswagen, volkswagen …)
        aliases = {canonical.lower(), brand.strip().lower()} | \
                  {k.lower() for k, v in BRAND_NORMALIZE.items()
                   if v.lower() == canonical.lower()}
        # Exakter Match auf brand-Feld (alle Aliases)
        brand_match = or_(*[func.lower(func.trim(Car.brand)) == a for a in aliases])
        # Fallback: brand=NULL, aber Marke steht im Titel
        title_fallback = and_(
            Car.brand.is_(None),
            func.lower(Car.title).like(f'%{canonical.lower()}%')
        )
        query = query.filter(or_(brand_match, title_fallback))
    if model:
        query = query.filter(
            or_(func.lower(Car.model).contains(model.lower()),
                func.lower(Car.title).contains(model.lower()))
        )
    if price_min:
        query = query.filter(Car.price >= price_min)
    if price_max:
        query = query.filter(Car.price <= price_max)
    if year_min:
        query = query.filter(Car.year >= year_min)
    if mileage_max:
        query = query.filter(Car.mileage <= mileage_max)
    if fuel_type:
        query = query.filter(func.lower(Car.fuel_type).contains(fuel_type.lower()))
    if platform:
        query = query.filter(Car.platform == platform)

    # "Suche"-Inserate (Gesuche/Wanted Ads) herausfiltern
    query = query.filter(
        ~or_(
            func.lower(Car.title).like('suche %'),
            func.lower(Car.title).like('suche:%'),
            func.lower(Car.title).like('[suche]%'),
            func.lower(Car.title).like('gesuch%'),
            func.lower(Car.title).like('%wird gesucht%'),
            func.lower(Car.title).like('% suche %'),
        )
    )

    if sort == 'price_asc':
        query = query.order_by(Car.price.asc())
    elif sort == 'price_desc':
        query = query.order_by(Car.price.desc())
    elif sort == 'mileage_asc':
        query = query.order_by(Car.mileage.asc())
    elif sort == 'year_desc':
        query = query.order_by(Car.year.desc())
    else:
        query = query.order_by(Car.first_seen.desc())

    recent_cars = query.limit(120).all()
    return render_template('live.html', cars=recent_cars, status=status,
                           car_data=CAR_DATA, car_brands=sorted(CAR_DATA.keys()),
                           f_brand=brand, f_model=model,
                           f_price_min=price_min, f_price_max=price_max,
                           f_year_min=year_min, f_mileage_max=mileage_max,
                           f_fuel_type=fuel_type, f_platform=platform, f_sort=sort)


@app.route('/api/stream')
def stream():
    """Server-Sent Events Endpoint für Live-Updates."""
    from services.live_scraper import new_cars_queue

    def event_stream():
        while True:
            try:
                car = new_cars_queue.get(timeout=30)
                data = json.dumps(car, ensure_ascii=False)
                yield f"data: {data}\n\n"
            except Exception:
                yield f": heartbeat\n\n"

    return Response(event_stream(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.route('/api/recent')
def api_recent():
    """Letzte Autos als JSON (Polling-Fallback)."""
    limit = request.args.get('limit', 20, type=int)
    after_id = request.args.get('after_id', 0, type=int)
    query = Car.query
    if after_id:
        query = query.filter(Car.id > after_id)
    cars = query.order_by(Car.first_seen.desc()).limit(limit).all()
    return jsonify([c.to_dict() for c in cars])


@app.route('/api/scraper-status')
def api_scraper_status():
    """Live-Scraper Status."""
    from services.live_scraper import get_scraper_status
    return jsonify(get_scraper_status())


@app.route('/search')
def search():
    """Suche durchführen und Ergebnisse anzeigen."""
    from services.search_service import search_cars

    brand = request.args.get('brand', '').strip()
    model = request.args.get('model', '').strip()
    price_min = request.args.get('price_min', type=int)
    price_max = request.args.get('price_max', type=int)
    year_min = request.args.get('year_min', type=int)
    mileage_max = request.args.get('mileage_max', type=int)
    fuel_type = request.args.get('fuel_type', '').strip()
    sort_by = request.args.get('sort', 'price_asc')

    platforms = request.args.getlist('platforms')
    if not platforms:
        platforms = ['mobile_de', 'autoscout24', 'kleinanzeigen']

    results = search_cars(
        brand=brand or None, model=model or None,
        price_min=price_min, price_max=price_max,
        year_min=year_min, mileage_max=mileage_max,
        fuel_type=fuel_type or None, platforms=platforms
    )

    if sort_by == 'price_asc':
        results.sort(key=lambda c: c.price or float('inf'))
    elif sort_by == 'price_desc':
        results.sort(key=lambda c: c.price or 0, reverse=True)
    elif sort_by == 'year_desc':
        results.sort(key=lambda c: c.year or 0, reverse=True)
    elif sort_by == 'mileage_asc':
        results.sort(key=lambda c: c.mileage or float('inf'))

    return render_template('results.html', cars=results, search_params=request.args)


@app.route('/car/<int:car_id>')
def car_detail(car_id):
    """Fahrzeug-Detailansicht mit allen Bildern."""
    from services.price_tracker import get_car_detail
    car = get_car_detail(car_id)
    if not car:
        flash('Fahrzeug nicht gefunden.', 'error')
        return redirect(url_for('index'))
    return render_template('detail.html', car=car)


@app.route('/track/<int:car_id>', methods=['POST'])
def track(car_id):
    """Fahrzeug tracken/untracken."""
    from services.price_tracker import track_car, untrack_car
    action = request.form.get('action', 'track')
    if action == 'untrack':
        untrack_car(car_id)
        flash('Tracking entfernt.', 'info')
    else:
        track_car(car_id)
        flash('Fahrzeug wird jetzt getrackt!', 'success')
    return redirect(request.referrer or url_for('tracked'))


@app.route('/tracked')
def tracked():
    """Getrackte Fahrzeuge anzeigen."""
    from services.price_tracker import get_tracked_cars
    cars = get_tracked_cars()
    return render_template('tracked.html', cars=cars)


@app.route('/alerts')
def alerts():
    """Alert-Verwaltung."""
    from services.notification import get_alerts
    from services.playwright_scraper import CAR_DATA
    alert_list = get_alerts()
    return render_template('alerts.html', alerts=alert_list,
                           car_brands=sorted(CAR_DATA.keys()),
                           car_data=CAR_DATA)


@app.route('/alerts/create', methods=['POST'])
def create_alert():
    """Neuen Alert erstellen."""
    from services.notification import create_alert as _create_alert
    email = request.form.get('email', '').strip()
    if not email:
        flash('Bitte E-Mail-Adresse angeben.', 'error')
        return redirect(url_for('alerts'))
    _create_alert(
        brand=request.form.get('brand', '').strip() or None,
        model=request.form.get('model', '').strip() or None,
        min_price=request.form.get('min_price', type=int),
        max_price=request.form.get('max_price', type=int),
        min_year=request.form.get('min_year', type=int),
        max_mileage=request.form.get('max_mileage', type=int),
        fuel_type=request.form.get('fuel_type', '').strip() or None,
        email=email
    )
    flash('Alert erstellt! Du wirst bei neuen Ergebnissen benachrichtigt.', 'success')
    return redirect(url_for('alerts'))


@app.route('/alerts/toggle/<int:alert_id>', methods=['POST'])
def toggle_alert(alert_id):
    from services.notification import toggle_alert as _toggle
    _toggle(alert_id)
    return redirect(url_for('alerts'))


@app.route('/alerts/delete/<int:alert_id>', methods=['POST'])
def delete_alert(alert_id):
    from services.notification import delete_alert as _delete
    _delete(alert_id)
    flash('Alert gelöscht.', 'info')
    return redirect(url_for('alerts'))


@app.route('/api/price-history/<int:car_id>')
def api_price_history(car_id):
    from models import PriceHistory
    history = PriceHistory.query.filter_by(car_id=car_id).order_by(PriceHistory.recorded_at).all()
    return jsonify([
        {'price': h.price, 'date': h.recorded_at.strftime('%d.%m.%Y %H:%M')}
        for h in history
    ])


# --- MARKTANALYSE NEU (DB-basiert, Schwarz-Weiß UI) ---
@app.route('/marktanalyse')
def marktanalyse():
    """Neue Marktanalyse-Seite: Daten aus DB, elegant schwarz-weiß."""
    from services.playwright_scraper import CAR_DATA
    from services.background_scraper import get_bg_status
    return render_template('marktanalyse.html',
                           car_data=CAR_DATA,
                           car_brands=sorted(CAR_DATA.keys()),
                           bg_status=get_bg_status())


@app.route('/api/markt-stats')
def api_markt_stats():
    """Marktstatistiken aus der DB mit Filtern."""
    import statistics as stats_mod
    from sqlalchemy import func

    brand = request.args.get('brand', '').strip()
    model = request.args.get('model', '').strip()
    variant = request.args.get('variant', '').strip()  # Freitext z.B. "1.4 Turbo", "GTC"
    year_exact = request.args.get('year_exact', type=int)
    year_from = request.args.get('year_from', type=int)
    year_to = request.args.get('year_to', type=int)
    km_max = request.args.get('km_max', type=int)
    fuel_type = request.args.get('fuel_type', '').strip()
    price_min = request.args.get('price_min', type=int)
    price_max_filter = request.args.get('price_max', type=int)
    transmission = request.args.get('transmission', '').strip()
    exclude_id = request.args.get('exclude_id', type=int)

    from sqlalchemy import or_
    query = Car.query.filter(Car.price.isnot(None), Car.price >= 500, Car.price <= 500000)

    if brand:
        query = query.filter(func.lower(Car.brand) == brand.lower())
    if model:
        # Contains-Suche: "Astra" findet auch "Astra GTC", "Astra 1.4" etc.
        query = query.filter(
            or_(
                func.lower(Car.model).contains(model.lower()),
                func.lower(Car.title).contains(model.lower())
            )
        )
    if variant:
        # Freitext-Suche im Titel für Variante/Ausstattung
        query = query.filter(func.lower(Car.title).contains(variant.lower()))
    if year_exact:
        query = query.filter(Car.year == year_exact)
    else:
        if year_from:
            query = query.filter(Car.year >= year_from)
        if year_to:
            query = query.filter(Car.year <= year_to)
    if km_max:
        query = query.filter(Car.mileage <= km_max)
    if fuel_type:
        query = query.filter(func.lower(Car.fuel_type).contains(fuel_type.lower()))
    if price_min:
        query = query.filter(Car.price >= price_min)
    if price_max_filter:
        query = query.filter(Car.price <= price_max_filter)
    if transmission:
        query = query.filter(func.lower(Car.transmission).contains(transmission.lower()))
    if exclude_id:
        query = query.filter(Car.id != exclude_id)

    cars = query.order_by(Car.price.asc()).all()

    if not cars:
        return jsonify({'count': 0, 'stats': None, 'listings': [], 'by_platform': {}, 'price_ranges': {}})

    prices = [c.price for c in cars if c.price]
    if not prices:
        return jsonify({'count': 0, 'stats': None, 'listings': [], 'by_platform': {}, 'price_ranges': {}})

    n = len(prices)
    q1 = prices[n // 4] if n > 3 else prices[0]
    q3 = prices[(3 * n) // 4] if n > 3 else prices[-1]

    analysis = {
        'count': n,
        'avg': round(stats_mod.mean(prices)),
        'median': round(stats_mod.median(prices)),
        'min': min(prices),
        'max': max(prices),
        'std_dev': round(stats_mod.stdev(prices)) if n > 1 else 0,
        'q1': q1,
        'q3': q3,
    }

    # Nach Plattform
    by_platform = {}
    for c in cars:
        p = c.platform or 'unknown'
        if p not in by_platform:
            by_platform[p] = {'count': 0, 'prices': []}
        by_platform[p]['count'] += 1
        by_platform[p]['prices'].append(c.price)
    for p in by_platform:
        pp = by_platform[p]['prices']
        by_platform[p]['avg'] = round(stats_mod.mean(pp))
        by_platform[p]['min'] = min(pp)
        by_platform[p]['max'] = max(pp)
        del by_platform[p]['prices']

    # Preisbereiche
    price_ranges = {}
    step = max(1000, (max(prices) - min(prices)) // 8) if max(prices) > min(prices) else 5000
    rs = (min(prices) // 1000) * 1000
    while rs <= max(prices):
        re_ = rs + step
        label = f"{rs:,} - {re_:,} €".replace(",", ".")
        cnt = len([p for p in prices if rs <= p < re_])
        if cnt > 0:
            price_ranges[label] = cnt
        rs = re_

    # Top Listings (günstigste + teuerste)
    listings = []
    for c in cars[:10]:  # günstigste 10
        listings.append(c.to_dict())
    for c in cars[-5:]:  # teuerste 5
        d = c.to_dict()
        if d not in listings:
            listings.append(d)

    return jsonify({
        'count': n,
        'stats': analysis,
        'listings': listings,
        'by_platform': by_platform,
        'price_ranges': price_ranges,
    })


@app.route('/api/bg-scrape', methods=['POST'])
def api_bg_scrape():
    """Manuell einen Background-Scrape auslösen."""
    import threading
    from services.background_scraper import run_background_scrape, bg_status

    if bg_status.get('running'):
        return jsonify({'status': 'already_running'})

    brands = request.json.get('brands') if request.json else None
    thread = threading.Thread(target=run_background_scrape, args=(app, brands), daemon=True)
    thread.start()
    return jsonify({'status': 'started'})


@app.route('/api/bg-status')
def api_bg_status():
    """Status des Background-Scrapers."""
    from services.background_scraper import get_bg_status
    return jsonify(get_bg_status())


# --- LEGACY: Live-Analyse (Playwright direkt) ---
@app.route('/market-live')
def market_live():
    """Live-Marktanalyse mit Playwright Headless-Browser."""
    from services.playwright_scraper import CAR_DATA
    return render_template('market_live.html', car_data=CAR_DATA, car_brands=sorted(CAR_DATA.keys()))


@app.route('/api/live-search', methods=['POST'])
def api_live_search():
    """API-Endpoint für Playwright Live-Suche."""
    from services.playwright_scraper import run_live_search
    data = request.json
    brand = data.get('brand', '')
    if not brand:
        return jsonify({'error': 'Bitte Marke angeben'}), 400

    results, analysis = run_live_search(
        brand=brand,
        model=data.get('model') or None,
        year_from=data.get('year_from'),
        year_to=data.get('year_to'),
        km_to=data.get('km_to'),
        sources=data.get('sources', ['autoscout24', 'kleinanzeigen']),
    )

    return jsonify({
        'results': results,
        'analysis': analysis,
        'count': len(results),
        'query': {'brand': brand, 'model': data.get('model', '')}
    })


# --- MARKTANALYSE ---
@app.route('/market')
def market():
    """Marktanalyse: Preistrend für eine Marke/Modell oder Gesamtmarkt."""
    from services.market_service import get_market_data, get_market_stats, get_full_market_overview

    brand = request.args.get('brand', '').strip()
    model = request.args.get('model', '').strip()
    fuel_type = request.args.get('fuel_type', '').strip()
    days = request.args.get('days', 90, type=int)

    market_data = []
    stats = None
    overview = None

    if brand or model:
        # Gefilterte Analyse für eine bestimmte Marke/Modell
        market_data = get_market_data(brand=brand or None, model=model or None,
                                      fuel_type=fuel_type or None, days=days)
        stats = get_market_stats(brand=brand or None, model=model or None,
                                 fuel_type=fuel_type or None, days=days)
    else:
        # Gesamtmarkt-Übersicht (kein Filter)
        overview = get_full_market_overview(days=days)

    return render_template('market.html',
                           market_data=market_data, stats=stats, overview=overview,
                           brand=brand, model=model, fuel_type=fuel_type, days=days)


@app.route('/api/market-data')
def api_market_data():
    """Marktdaten als JSON für dynamisches Nachladen."""
    from services.market_service import get_market_data
    data = get_market_data(
        brand=request.args.get('brand') or None,
        model=request.args.get('model') or None,
        fuel_type=request.args.get('fuel_type') or None,
        days=request.args.get('days', 90, type=int)
    )
    return jsonify(data)


# --- SCHEDULER & LIVE SCRAPER ---
def start_scheduler():
    from services.notification import check_alerts
    from services.background_scraper import start_background_scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=lambda: check_alerts(mail, app),
        trigger='interval',
        minutes=app.config.get('ALERT_CHECK_INTERVAL', 30),
        id='alert_checker',
        replace_existing=True
    )
    # Background-Scraper: alle 2 Stunden AutoScout24 + Kleinanzeigen
    start_background_scheduler(app, scheduler)
    scheduler.start()
    logger.info(f"Scheduler gestartet (Alerts alle {app.config.get('ALERT_CHECK_INTERVAL', 30)} Min, BG-Scraper alle 2h)")


# Startup: Scheduler + Live-Scraper mit Fehlerbehandlung
def _startup():
    try:
        start_scheduler()
    except Exception as e:
        logger.error(f"Scheduler-Start fehlgeschlagen: {e}")

    if app.config.get('LIVE_SCRAPE_ENABLED', True):
        try:
            from services.live_scraper import start_live_scraper
            start_live_scraper(app)
        except Exception as e:
            logger.error(f"Live-Scraper-Start fehlgeschlagen: {e}")


_startup()


if __name__ == '__main__':
    app.run(debug=True, port=5000, use_reloader=False, threaded=True)
