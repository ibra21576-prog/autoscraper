"""
Playwright-basierter Live-Scraper für Echtzeit-Marktanalyse.
Nutzt Headless Browser um Captchas/JS-Rendering zu umgehen.
"""

import asyncio
import re
import statistics
import logging

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright nicht installiert — Playwright-Scraping deaktiviert")

CAR_DATA = {
    "Audi": ["A1","A3","A4","A5","A6","A7","A8","Q2","Q3","Q5","Q7","Q8","TT","RS3","RS4","RS5","RS6","RS7","e-tron"],
    "BMW": ["1er","2er","3er","4er","5er","6er","7er","8er","X1","X2","X3","X4","X5","X6","X7","Z4","M2","M3","M4","M5","iX"],
    "Mercedes-Benz": ["A-Klasse","B-Klasse","C-Klasse","E-Klasse","S-Klasse","CLA","CLS","GLA","GLB","GLC","GLE","GLS","G-Klasse","AMG GT","EQC","EQS"],
    "Volkswagen": ["Golf","Polo","Passat","Tiguan","T-Roc","T-Cross","Touareg","Arteon","ID.3","ID.4","ID.5","Up","Caddy","Multivan"],
    "Opel": ["Corsa","Astra","Insignia","Mokka","Crossland","Grandland"],
    "Ford": ["Fiesta","Focus","Mondeo","Kuga","Puma","Mustang","Explorer","EcoSport"],
    "Toyota": ["Yaris","Corolla","Camry","RAV4","C-HR","Supra","Aygo","Land Cruiser","Hilux"],
    "Hyundai": ["i10","i20","i30","Tucson","Kona","Santa Fe","Ioniq","Ioniq 5"],
    "Kia": ["Picanto","Rio","Ceed","Sportage","Sorento","Stinger","EV6","Niro"],
    "Seat": ["Ibiza","Leon","Arona","Ateca","Tarraco"],
    "Skoda": ["Fabia","Octavia","Superb","Kamiq","Karoq","Kodiaq","Enyaq"],
    "Renault": ["Clio","Megane","Captur","Kadjar","Scenic","Twingo","Zoe"],
    "Peugeot": ["208","308","508","2008","3008","5008"],
    "Fiat": ["500","Panda","Tipo","500X","500L"],
    "Porsche": ["911","Cayenne","Macan","Panamera","Taycan","Boxster","Cayman"],
    "Volvo": ["S60","S90","V40","V60","V90","XC40","XC60","XC90"],
    "Mazda": ["2","3","6","CX-3","CX-5","CX-30","MX-5"],
    "Nissan": ["Micra","Juke","Qashqai","X-Trail","Leaf"],
    "Honda": ["Jazz","Civic","CR-V","HR-V","e"],
    "Tesla": ["Model 3","Model Y","Model S","Model X"],
    "MINI": ["Cooper","Countryman","Clubman"],
    "Jeep": ["Renegade","Compass","Wrangler","Grand Cherokee"],
    "Land Rover": ["Defender","Discovery","Evoque","Velar","Range Rover Sport","Range Rover"],
    "Alfa Romeo": ["Giulia","Stelvio","Tonale"],
    "Dacia": ["Sandero","Duster","Logan","Spring","Jogger"],
    "Cupra": ["Born","Formentor","Leon","Ateca"],
}


def _price_to_int(text):
    if not text:
        return None
    text = text.replace(".", "").replace(",", "").replace("€", "").replace("EUR", "")
    text = text.replace("\xa0", "").replace(" ", "").strip()
    match = re.search(r'(\d{3,7})', text)
    if match:
        val = int(match.group(1))
        if 200 <= val <= 500000:
            return val
    return None


def _km_to_int(text):
    if not text:
        return None
    text = text.replace(".", "").replace(",", "").replace("km", "").replace(" ", "").strip()
    match = re.search(r'(\d{1,7})', text)
    return int(match.group(1)) if match else None


STEALTH_SCRIPT = """
    // Webdriver komplett verstecken
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    delete navigator.__proto__.webdriver;

    // Chrome Runtime simulieren
    window.chrome = {
        runtime: {
            onConnect: { addListener: function() {} },
            onMessage: { addListener: function() {} },
            connect: function() { return { onMessage: { addListener: function() {} } } }
        },
        loadTimes: function() { return {} },
        csi: function() { return {} },
    };

    // Plugins simulieren (Chrome hat mindestens 3)
    Object.defineProperty(navigator, 'plugins', {
        get: () => {
            const plugins = [
                {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format'},
                {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: ''},
                {name: 'Native Client', filename: 'internal-nacl-plugin', description: ''},
            ];
            plugins.length = 3;
            return plugins;
        }
    });

    // Languages
    Object.defineProperty(navigator, 'languages', {get: () => ['de-DE','de','en-US','en']});
    Object.defineProperty(navigator, 'language', {get: () => 'de-DE'});

    // Hardware Concurrency
    Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
    Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
    Object.defineProperty(navigator, 'maxTouchPoints', {get: () => 0});
    Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});

    // Permissions API faken
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({state: Notification.permission}) :
            originalQuery(parameters)
    );

    // WebGL Vendor/Renderer
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        if (parameter === 37445) return 'Intel Inc.';
        if (parameter === 37446) return 'Intel Iris OpenGL Engine';
        return getParameter.call(this, parameter);
    };

    // Iframe contentWindow Patch
    const originalAttachShadow = Element.prototype.attachShadow;
    Element.prototype.attachShadow = function() {
        return originalAttachShadow.apply(this, arguments);
    };

    // Console.debug Trap vermeiden
    window.console.debug = function() {};
"""


async def _make_context(pw, extra_stealth=False):
    browser = await pw.chromium.launch(
        headless=True,
        args=[
            '--no-sandbox',
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--disable-infobars',
            '--window-size=1920,1080',
            '--disable-extensions',
            '--disable-gpu',
            '--lang=de-DE,de',
        ]
    )
    ctx = await browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        viewport={'width': 1920, 'height': 1080},
        locale='de-DE',
        timezone_id='Europe/Berlin',
        geolocation={'latitude': 51.1657, 'longitude': 10.4515},
        permissions=['geolocation'],
        color_scheme='light',
        extra_http_headers={
            'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
            'sec-ch-ua': '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        }
    )
    return browser, ctx


async def _stealth(ctx):
    page = await ctx.new_page()
    await page.add_init_script(STEALTH_SCRIPT)
    return page


async def _human_scroll(page, steps=4):
    """Simuliert menschliches Scroll-Verhalten."""
    import random
    for _ in range(steps):
        dist = random.randint(300, 700)
        await page.evaluate(f"window.scrollBy(0, {dist})")
        await page.wait_for_timeout(random.randint(400, 900))


async def _consent(page):
    for sel in [
        'button:has-text("Einverstanden")', 'button:has-text("Alle akzeptieren")',
        'button:has-text("Accept All")', '#onetrust-accept-btn-handler',
        '#gdpr-banner-accept', '[data-testid="gdpr-consent-accept-button"]',
        'button[id*="accept"]', 'button[class*="accept"]', 'button[class*="consent"]',
        '[aria-label="Einverstanden"]', '[aria-label="Accept"]',
    ]:
        try:
            btn = page.locator(sel)
            if await btn.count() > 0:
                await btn.first.click()
                await page.wait_for_timeout(1200)
                return
        except:
            continue


def _extract(lines):
    price = km = year = None
    for line in lines:
        if not price and ('€' in line or 'EUR' in line or 'VB' in line):
            price = _price_to_int(line)
        if not km and 'km' in line.lower():
            km = _km_to_int(line)
        if not year:
            m = re.search(r'(EZ\s*)?(\d{2})/(\d{4})', line)
            if m:
                year = int(m.group(3))
            else:
                m2 = re.search(r'20[0-2]\d|19[89]\d', line)
                if m2:
                    year = int(m2.group(0))
    return price, km, year


async def scrape_autoscout24(brand, model, year_from=None, year_to=None, km_to=None):
    results = []
    try:
        async with async_playwright() as p:
            import random
            browser, ctx = await _make_context(p)
            page = await _stealth(ctx)

            # AutoScout24 nutzt jetzt Query-Parameter statt Pfad-Slugs
            url = f"https://www.autoscout24.de/lst?make={brand}&model={model or ''}&sort=age&desc=1&atype=C&cy=D"
            if year_from: url += f"&fregfrom={year_from}"
            if year_to:   url += f"&fregto={year_to}"
            if km_to:     url += f"&kmto={km_to}"

            logger.info(f"[PW] AutoScout24: {url}")
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(random.randint(2500, 4000))
            await _consent(page)
            await _human_scroll(page, steps=5)

            # article-Elemente enthalten die Listings
            listings = page.locator('article[class*="cldt"], article[class*="list-page"]')
            count = await listings.count()
            if count == 0:
                listings = page.locator('article')
                count = await listings.count()
            logger.info(f"[PW] AutoScout24: {count} Listings")

            for i in range(min(count, 30)):
                try:
                    text = await listings.nth(i).inner_text()
                    lines = [l.strip() for l in text.split('\n') if l.strip()]
                    # Titel: "Gesponsert" und andere Labels überspringen
                    title = "Unbekannt"
                    for line in lines:
                        if line not in ('Gesponsert', 'Details zum offenen Angebot', 'Vergleichen', 'Merken', 'Neu') and len(line) > 3:
                            title = line
                            break

                    price = km = year = None
                    for line in lines:
                        # Preis: "€ 25.990" oder "€ 25.9901" (1=Fußnote)
                        if not price and '€' in line:
                            cleaned = re.sub(r'[^\d.]', '', line.replace('€', '').strip())
                            # Entferne trailing Fußnoten-Ziffer
                            cleaned = re.sub(r'(\d)(\d)$', r'\1', cleaned) if len(cleaned) > 4 else cleaned
                            cleaned = cleaned.replace('.', '')
                            if cleaned.isdigit() and 200 <= int(cleaned) <= 500000:
                                price = int(cleaned)
                        if not km and 'km' in line.lower():
                            km = _km_to_int(line)
                        if not year:
                            m = re.search(r'(\d{2})/(\d{4})', line)
                            if m:
                                year = int(m.group(2))

                    if price and price >= 500:
                        results.append({'title': title[:120], 'price': price, 'km': km, 'year': year, 'source': 'AutoScout24'})
                except:
                    continue

            logger.info(f"[PW] AutoScout24: {len(results)} Ergebnisse")
            await browser.close()
    except Exception as e:
        logger.error(f"[PW] AutoScout24 Fehler: {e}")
    return results


async def scrape_mobile_de(brand, model, year_from=None, year_to=None, km_to=None):
    """Scrapet mobile.de mit Webkit (Safari-Engine, wird am wenigsten blockiert)."""
    results = []
    try:
        async with async_playwright() as p:
            import random
            # Webkit (Safari) umgeht Akamai Bot Manager am besten
            browser = await p.webkit.launch(headless=True)
            ctx = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                locale='de-DE',
                timezone_id='Europe/Berlin',
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15',
            )
            page = await ctx.new_page()

            # Such-URL
            q = f"{brand}+{model}" if model else brand
            url = (
                f"https://suchen.mobile.de/fahrzeuge/search.html?"
                f"lang=de&isSearchRequest=true&scopeId=C"
                f"&makeModelVariant1.makeModelDescription={q}"
                f"&sortOption.sortBy=creationDate&sortOption.sortOrder=DESCENDING"
            )
            if year_from: url += f"&minFirstRegistrationDate={year_from}-01-01"
            if year_to:   url += f"&maxFirstRegistrationDate={year_to}-12-31"
            if km_to:     url += f"&maxMileage={km_to}"

            logger.info(f"[PW] Mobile.de (Webkit): {url}")
            resp = await page.goto(url, wait_until='networkidle', timeout=45000)
            status = resp.status if resp else 0
            logger.info(f"[PW] Mobile.de Status: {status}")

            if status != 200:
                await browser.close()
                return results

            await page.wait_for_timeout(3000)

            # Check ob blockiert
            body_text = await page.inner_text('body')
            if 'Zugriff verweigert' in body_text:
                logger.warning("[PW] Mobile.de: Zugriff verweigert")
                await browser.close()
                return results

            # Consent klicken per JS (auch in Shadow DOM)
            logger.info("[PW] Mobile.de: Consent suchen...")
            await page.evaluate("""
                () => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        const t = (b.textContent || '').toLowerCase();
                        if (t.includes('einverstanden') || t.includes('alle akzeptieren')) {
                            b.click(); return;
                        }
                    }
                    const allEls = document.querySelectorAll('*');
                    for (const el of allEls) {
                        if (el.shadowRoot) {
                            const sbtns = el.shadowRoot.querySelectorAll('button');
                            for (const b of sbtns) {
                                const t = (b.textContent || '').toLowerCase();
                                if (t.includes('einverstanden') || t.includes('akzeptieren')) {
                                    b.click(); return;
                                }
                            }
                        }
                    }
                }
            """)
            await page.wait_for_timeout(5000)

            # Scroll
            for _ in range(6):
                await page.evaluate(f"window.scrollBy(0, {random.randint(300, 600)})")
                await page.wait_for_timeout(random.randint(300, 600))
            await page.wait_for_timeout(2000)

            # Listings
            articles = page.locator('[data-testid^="result-listing-"]')
            total = await articles.count()
            if total == 0:
                articles = page.locator('article')
                total = await articles.count()
            logger.info(f"[PW] Mobile.de: {total} Listing-Elemente")

            skip_texts = {'Weitere Filter', 'Fahrzeugzustand', 'Sortieren nach', 'Suche speichern'}

            for i in range(total):
                try:
                    text = await articles.nth(i).inner_text()
                    lines = [l.strip() for l in text.split('\n') if l.strip()]

                    # Überspringe Filter/Header-Artikel
                    if not lines or lines[0] in skip_texts or 'Angebote' in lines[0]:
                        continue

                    # Titel extrahieren: "GesponsertBMW 320d" -> "BMW 320d"
                    title = "Unbekannt"
                    for line in lines:
                        cleaned = line.replace('Gesponsert', '').replace('Top', '').strip()
                        if cleaned and len(cleaned) > 3 and cleaned not in skip_texts:
                            title = cleaned
                            break

                    price = km = year = None
                    for line in lines:
                        # Preis: "46.600 €¹" oder "15.900 €"
                        if not price and '€' in line:
                            price = _price_to_int(line)
                        # KM + Details: "EZ 11/2019 • 132.250 km • 200 kW (272 PS) • Diesel"
                        if '•' in line or 'km' in line.lower():
                            if not km:
                                km = _km_to_int(line)
                            if not year:
                                m = re.search(r'EZ\s*(\d{2})/(\d{4})', line)
                                if m:
                                    year = int(m.group(2))
                                else:
                                    m2 = re.search(r'(\d{2})/(\d{4})', line)
                                    if m2:
                                        year = int(m2.group(2))

                    if price and price >= 500:
                        results.append({
                            'title': title[:120],
                            'price': price,
                            'km': km,
                            'year': year,
                            'source': 'mobile.de'
                        })
                except:
                    continue

            logger.info(f"[PW] Mobile.de: {len(results)} Ergebnisse extrahiert")
            await browser.close()
    except Exception as e:
        logger.error(f"[PW] Mobile.de Fehler: {e}")
    return results


async def scrape_kleinanzeigen(brand, model, year_from=None, year_to=None, km_to=None):
    results = []
    try:
        async with async_playwright() as p:
            browser, ctx = await _make_context(p)
            page = await _stealth(ctx)

            q = f"{brand} {model}".strip() if model else brand
            url = f"https://www.kleinanzeigen.de/s-autos/{q}/k0c216"
            logger.info(f"[PW] Kleinanzeigen: {url}")
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(3000)
            await _consent(page)

            count = 0
            listings = None
            for sel in ['[data-adid]', 'article.aditem', '.ad-listitem .aditem', '[class*="aditem"]']:
                listings = page.locator(sel)
                count = await listings.count()
                if count > 0: break
            if count == 0:
                listings = page.locator('article, li[class*="ad-listitem"]')
                count = await listings.count()

            logger.info(f"[PW] Kleinanzeigen: {count} Listings")
            for i in range(min(count, 30)):
                try:
                    text = await listings.nth(i).inner_text()
                    lines = [l.strip() for l in text.split('\n') if l.strip()]
                    title = lines[0] if lines else "Unbekannt"
                    price, km, year = _extract(lines)
                    if price and price >= 500:
                        results.append({'title': title[:120], 'price': price, 'km': km, 'year': year, 'source': 'Kleinanzeigen'})
                except: continue
            await browser.close()
    except Exception as e:
        logger.error(f"[PW] Kleinanzeigen Fehler: {e}")
    return results


def analyze_results(results):
    if not results:
        return None
    prices = [r['price'] for r in results if r.get('price')]
    if not prices:
        return None

    prices_sorted = sorted(prices)
    n = len(prices_sorted)
    q1 = prices_sorted[n // 4] if n > 3 else prices_sorted[0]
    q3 = prices_sorted[(3 * n) // 4] if n > 3 else prices_sorted[-1]

    analysis = {
        'total': n,
        'avg_price': round(statistics.mean(prices)),
        'median_price': round(statistics.median(prices)),
        'min_price': min(prices),
        'max_price': max(prices),
        'std_dev': round(statistics.stdev(prices)) if n > 1 else 0,
        'q1': q1, 'q3': q3,
        'realistic_min': q1, 'realistic_max': q3,
        'price_ranges': {},
        'by_source': {},
    }

    step = max(1000, (max(prices) - min(prices)) // 8)
    rs = (min(prices) // 1000) * 1000
    while rs <= max(prices):
        re_ = rs + step
        label = f"{rs:,} - {re_:,} €".replace(",", ".")
        c = len([p for p in prices if rs <= p < re_])
        if c > 0:
            analysis['price_ranges'][label] = c
        rs = re_

    for r in results:
        src = r.get('source', 'Unbekannt')
        if src not in analysis['by_source']:
            analysis['by_source'][src] = {'count': 0, 'prices': []}
        analysis['by_source'][src]['count'] += 1
        if r.get('price'):
            analysis['by_source'][src]['prices'].append(r['price'])
    for src in analysis['by_source']:
        p = analysis['by_source'][src]['prices']
        if p:
            analysis['by_source'][src]['avg'] = round(statistics.mean(p))
            analysis['by_source'][src]['min'] = min(p)
            analysis['by_source'][src]['max'] = max(p)

    return analysis


def run_live_search(brand, model=None, year_from=None, year_to=None, km_to=None, sources=None):
    if not PLAYWRIGHT_AVAILABLE:
        logger.warning("Playwright nicht verfügbar — kein Scraping möglich")
        return [], None

    if sources is None:
        # mobile.de standardmäßig deaktiviert (Akamai Anti-Bot)
        sources = ['autoscout24', 'kleinanzeigen']

    async def _run():
        tasks = []
        if 'autoscout24' in sources:
            tasks.append(scrape_autoscout24(brand, model or '', year_from, year_to, km_to))
        if 'mobile' in sources:
            tasks.append(scrape_mobile_de(brand, model or '', year_from, year_to, km_to))
        if 'kleinanzeigen' in sources:
            tasks.append(scrape_kleinanzeigen(brand, model or '', year_from, year_to, km_to))
        all_results = await asyncio.gather(*tasks, return_exceptions=True)
        combined = []
        for r in all_results:
            if isinstance(r, list):
                combined.extend(r)
        return combined

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(_run())
        loop.close()
    except Exception as e:
        logger.error(f"Live-Search Fehler: {e}")
        results = []

    return results, analyze_results(results)
