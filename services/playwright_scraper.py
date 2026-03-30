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
    # ── Deutsche Marken ──────────────────────────────────────────────
    "Audi": ["A1","A2","A3","A4","A5","A6","A7","A8","Q2","Q3","Q4 e-tron","Q5","Q7","Q8","Q8 e-tron","TT","TTS","RS3","RS4","RS5","RS6","RS7","R8","e-tron","e-tron GT","S3","S4","S5","S6","S7","S8","SQ5","SQ7","SQ8"],
    "BMW": ["1er","2er","3er","4er","5er","6er","7er","8er","X1","X2","X3","X4","X5","X6","X7","Z3","Z4","M2","M3","M4","M5","M6","M8","iX","iX1","iX3","i3","i4","i5","i7","ActiveTourer","GranTourer","GranCoupe","316d","318i","320i","330i","335i","340i"],
    "Mercedes-Benz": ["A-Klasse","B-Klasse","C-Klasse","E-Klasse","S-Klasse","CLA","CLA Shooting Brake","CLS","GLA","GLB","GLC","GLC Coupe","GLE","GLE Coupe","GLS","G-Klasse","AMG GT","AMG GT 4-Türer","EQA","EQB","EQC","EQE","EQS","SL","SLC","V-Klasse","Vito","Sprinter","Marco Polo"],
    "Volkswagen": ["Golf","Golf Plus","Golf Variant","Polo","Passat","Passat Variant","Tiguan","Tiguan Allspace","T-Roc","T-Cross","Touareg","Touran","Arteon","Arteon Shooting Brake","ID.3","ID.4","ID.5","ID.7","ID. Buzz","Up","Caddy","Multivan","Sharan","Beetle","Phaeton","CC"],
    "Opel": ["Corsa","Astra","Astra Sports Tourer","Insignia","Insignia Sports Tourer","Mokka","Crossland","Grandland","Zafira","Zafira Life","Combo","Meriva","Adam","Karl","Agila","Vectra","Omega","Cascada","Ampera","Rocks-e"],
    "Porsche": ["911","718 Boxster","718 Cayman","Cayenne","Cayenne Coupe","Macan","Panamera","Taycan","Taycan Cross Turismo"],
    "Smart": ["fortwo","forfour","#1","#3"],
    "Brabus": ["800","900","Rocket","Shadow"],
    # ── Britische Marken ─────────────────────────────────────────────
    "Land Rover": ["Defender","Defender 90","Defender 110","Discovery","Discovery Sport","Range Rover","Range Rover Sport","Range Rover Velar","Range Rover Evoque","Freelander"],
    "Jaguar": ["XE","XF","XJ","E-Pace","F-Pace","F-Type","I-Pace","XK"],
    "MINI": ["Cooper","Cooper S","Cooper SE","Clubman","Countryman","Cabrio","Paceman","Roadster","Coupe","John Cooper Works"],
    "Bentley": ["Continental GT","Continental GTC","Flying Spur","Bentayga","Mulsanne"],
    "Rolls-Royce": ["Ghost","Phantom","Wraith","Dawn","Cullinan","Spectre"],
    "Aston Martin": ["DB11","DB12","Vantage","DBS","DBX","Valkyrie"],
    "McLaren": ["570S","600LT","720S","750S","Artura","GT"],
    # ── Französische Marken ──────────────────────────────────────────
    "Renault": ["Clio","Megane","Megane E-Tech","Captur","Kadjar","Scenic","Espace","Twingo","Zoe","Arkana","Austral","Rafale","Kangoo","Trafic","Master","Laguna","Koleos","Fluence"],
    "Peugeot": ["108","208","308","408","508","508 SW","2008","3008","4008","5008","Rifter","Partner","Expert","Traveller","Boxer","RCZ","e-208","e-2008"],
    "Citroën": ["C1","C2","C3","C3 Aircross","C4","C4 X","C5","C5 Aircross","C5 X","C6","Berlingo","SpaceTourer","Jumpy","Jumper","DS3","Ami","ë-C4"],
    "DS Automobiles": ["DS3","DS3 Crossback","DS4","DS5","DS7","DS9","DS7 Crossback"],
    "Alpine": ["A110","A110 S","A110 GT"],
    # ── Italienische Marken ──────────────────────────────────────────
    "Fiat": ["500","500C","500X","500L","500e","Panda","Tipo","Tipo Cross","Bravo","Punto","Doblo","Qubo","Ducato","Talento","Freemont"],
    "Alfa Romeo": ["Giulia","Stelvio","Tonale","Giulietta","MiTo","147","156","159","Brera","Spider","4C","GTV","Mito"],
    "Lancia": ["Ypsilon","Delta","Musa"],
    "Abarth": ["595","595C","595 Competizione","695","124 Spider"],
    "Ferrari": ["296 GTB","296 GTS","F8 Tributo","F8 Spider","812 Superfast","SF90 Stradale","Roma","Portofino","GTC4Lusso","488","458","California","Testarossa","F40","F50","Enzo"],
    "Lamborghini": ["Urus","Huracan","Aventador","Revuelto","Sterrato"],
    "Maserati": ["Ghibli","Quattroporte","Levante","Grecale","GranTurismo","GranCabrio","MC20"],
    # ── Schwedische Marken ───────────────────────────────────────────
    "Volvo": ["S40","S60","S90","V40","V40 Cross Country","V60","V60 Cross Country","V90","V90 Cross Country","XC40","XC60","XC90","C30","C70","EX30","EX40","EX90","EC40"],
    "Polestar": ["1","2","3","4"],
    "Saab": ["9-3","9-5","9-7X"],
    # ── Japanische Marken ─────────────────────────────────────────────
    "Toyota": ["Aygo","Aygo X","Yaris","Yaris Cross","Corolla","Corolla Cross","Corolla Touring Sports","Camry","RAV4","RAV4 Plug-in","C-HR","C-HR Plug-in","Supra","Land Cruiser","Land Cruiser 300","Hilux","Proace","bZ4X","GR86","GR Yaris"],
    "Honda": ["Jazz","Jazz e:HEV","Civic","Civic e:HEV","CR-V","CR-V e:HEV","HR-V","ZR-V","e","e:Ny1","FR-V","Accord","Legend","NSX"],
    "Nissan": ["Micra","Juke","Qashqai","X-Trail","Leaf","Ariya","GT-R","370Z","400Z","Murano","Pathfinder","Navara","NV200","NV300","NV400","Note","Pulsar"],
    "Mazda": ["2","2 Hybrid","3","6","CX-3","CX-30","CX-5","CX-60","CX-80","MX-5","MX-30","MX-5 RF","RX-8"],
    "Subaru": ["Impreza","Legacy","Outback","Forester","XV","BRZ","WRX","Levorg","Solterra","Crosstrek"],
    "Suzuki": ["Alto","Swift","Ignis","Celerio","Baleno","Vitara","S-Cross","Jimny","Swace","Across","SX4","Splash","Wagon R+"],
    "Mitsubishi": ["Colt","Space Star","ASX","Outlander","Outlander PHEV","Eclipse Cross","Eclipse Cross PHEV","Galant","Lancer","Carisma","Pajero","L200","i-MiEV","Grandis"],
    "Lexus": ["UX","UX 300e","NX","NX 450h+","RX","RX 500h","ES","LS","GX","LX","IS","RC","LC","LFA"],
    "Infiniti": ["Q30","Q50","Q60","Q70","QX30","QX50","QX60","QX70","QX80"],
    # ── Koreanische Marken ────────────────────────────────────────────
    "Hyundai": ["i10","i20","i20 N","i30","i30 N","i30 Fastback","Tucson","Kona","Kona Electric","Santa Fe","Ioniq","Ioniq 5","Ioniq 6","Nexo","Bayon","Santa Cruz","Staria","H-1"],
    "Kia": ["Picanto","Rio","Ceed","Ceed SW","ProCeed","Sportage","Sorento","Stinger","EV3","EV6","EV9","Niro","Niro EV","Carnival","XCeed","Stonic","Soul"],
    "Genesis": ["G70","G80","GV70","GV80","GV60","G90","Electrified GV70","Electrified G80"],
    "SsangYong": ["Tivoli","Korando","Rexton","Musso","Torres"],
    # ── US-amerikanische Marken ───────────────────────────────────────
    "Tesla": ["Model 3","Model Y","Model S","Model X","Cybertruck","Roadster"],
    "Ford": ["Fiesta","Fiesta ST","Focus","Focus ST","Mondeo","Mondeo Turnier","Kuga","Puma","Mustang","Mustang Mach-E","Explorer","EcoSport","Edge","S-Max","Galaxy","Transit","Transit Custom","Transit Connect","Ranger","Bronco","F-150 Lightning","Maverick"],
    "Jeep": ["Renegade","Compass","Wrangler","Grand Cherokee","Grand Cherokee L","Commander","Avenger","Gladiator"],
    "Dodge": ["Challenger","Charger","Durango","Journey","Viper"],
    "Chevrolet": ["Camaro","Corvette","Trax","Trailblazer","Equinox","Traverse","Tahoe","Suburban","Silverado","Colorado"],
    "Cadillac": ["CT4","CT5","Escalade","XT4","XT5","XT6","Lyriq"],
    "Chrysler": ["300C","Pacifica","Voyager"],
    # ── Chinesische Marken ─────────────────────────────────────────────
    "MG": ["MG3","MG4","MG5","MG ZS","MG HS","MG RX5","MG Marvel R","Cyberster"],
    "BYD": ["Atto 3","Atto 4","Han","Tang","Seal","Dolphin","Seagull","EA1"],
    "NIO": ["ET5","ET7","EL6","ES6","ES7","EC6","ET5 Touring"],
    "Xpeng": ["G3","P5","P7","G6","G9"],
    "Lynk & Co": ["01","02","03","05"],
    "Ora": ["Funky Cat","Lightning Cat"],
    "GWM": ["Poer","Ora"],
    # ── Sonstige / Weitere ────────────────────────────────────────────
    "Seat": ["Ibiza","Leon","Leon ST","Leon Sportstourer","Arona","Ateca","Tarraco","Mii","Alhambra","Toledo","Exeo","el-Born"],
    "Skoda": ["Fabia","Fabia Combi","Octavia","Octavia Combi","Superb","Superb Combi","Kamiq","Karoq","Kodiaq","Enyaq","Citigo","Rapid","Scala","Roomster","Yeti"],
    "Cupra": ["Born","Formentor","Leon","Leon Sportstourer","Ateca","Tavascan","Urban Rebel"],
    "Dacia": ["Sandero","Sandero Stepway","Duster","Logan","Logan MCV","Spring","Jogger","Bigster"],
    "Alfa Romeo": ["Giulia","Giulia Quadrifoglio","Stelvio","Stelvio Quadrifoglio","Tonale","Giulietta","MiTo","147","156","159","Brera","Spider","4C","Junior"],
    "Lada": ["Niva","2101","2105","2107","2110","Granta","Vesta","XRAY","Kalina"],
    "Rover": ["75","45","25","200","400","600","800"],
    "Daihatsu": ["Cuore","Sirion","Terios","YRV","Copen","Rocky"],
    "Isuzu": ["D-Max","MU-X","Trooper","Rodeo"],
    "Microcar": ["M.Go","DUÉ"],
    "Aixam": ["City","Crossline","Coupe","GTO","e-Coupe"],
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
