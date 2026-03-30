/* ====================================================
   AUTOSCRAPER — Sahara Theme JS
   ==================================================== */

// ---- MOBILE MENU ----
(function() {
    const toggle = document.getElementById('mobileToggle');
    const drawer = document.getElementById('mobileDrawer');
    if (!toggle || !drawer) return;

    toggle.addEventListener('click', function() {
        const isOpen = drawer.classList.contains('open');
        drawer.classList.toggle('open');
        toggle.classList.toggle('open');
        document.body.style.overflow = isOpen ? '' : 'hidden';
    });

    drawer.querySelectorAll('.mobile-nav-link').forEach(link => {
        link.addEventListener('click', () => {
            drawer.classList.remove('open');
            toggle.classList.remove('open');
            document.body.style.overflow = '';
        });
    });
})();

// ---- SCROLL REVEAL ----
(function() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.08, rootMargin: '0px 0px -40px 0px' });

    document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
})();

// ---- SEARCH FORM LOADING STATE ----
(function() {
    const form = document.getElementById('searchForm');
    const btn = document.getElementById('searchBtn');
    if (!form || !btn) return;

    form.addEventListener('submit', function() {
        btn.textContent = 'SUCHE LAEUFT...';
        btn.style.opacity = '0.7';
        btn.disabled = true;
    });
})();

// ---- HERO SMOOTH SCROLL ----
document.querySelector('[href="#search"]')?.addEventListener('click', function(e) {
    e.preventDefault();
    document.getElementById('search')?.scrollIntoView({ behavior: 'smooth' });
});

// ---- STICKY HEADER EFFECT ----
window.addEventListener('scroll', function() {
    const header = document.querySelector('.sahara-header');
    if (!header) return;
    if (window.scrollY > 10) {
        header.style.boxShadow = '0 2px 20px rgba(0,0,0,0.06)';
    } else {
        header.style.boxShadow = 'none';
    }
}, { passive: true });

// ---- PRICE CHART (Detailseite) ----
function renderPriceChart(canvasId, priceData) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !priceData || priceData.length === 0) return;

    const labels = priceData.map(d => d.date);
    const prices = priceData.map(d => d.price);

    new Chart(canvas, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'Preis',
                data: prices,
                borderColor: '#CD9B77',
                backgroundColor: 'rgba(205, 155, 119, 0.1)',
                fill: true,
                tension: 0.3,
                pointRadius: 4,
                pointBackgroundColor: '#CD9B77',
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                borderWidth: 2,
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#111',
                    titleColor: '#CD9B77',
                    bodyColor: '#fff',
                    padding: 12,
                    callbacks: {
                        label: ctx => ctx.parsed.y.toLocaleString('de-DE') + ' \u20AC'
                    }
                }
            },
            scales: {
                y: {
                    grid: { color: '#E6E2E1' },
                    ticks: {
                        font: { family: 'Inter', size: 11 },
                        color: '#5E5A59',
                        callback: v => v.toLocaleString('de-DE') + ' \u20AC'
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: { font: { family: 'Inter', size: 11 }, color: '#5E5A59', maxTicksLimit: 8, maxRotation: 0 }
                }
            }
        }
    });
}

// ---- MINI CHART (Tracking) ----
function renderMiniChart(canvasId, priceData) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !priceData || priceData.length < 2) return;

    const prices = priceData.map(d => d.price);
    const trend = prices[prices.length - 1] <= prices[prices.length - 2];
    const color = trend ? '#4A7C59' : '#B44A3E';

    new Chart(canvas, {
        type: 'line',
        data: {
            labels: priceData.map(d => d.date),
            datasets: [{
                data: prices,
                borderColor: color,
                backgroundColor: color + '18',
                fill: true,
                tension: 0.3,
                pointRadius: 0,
                borderWidth: 1.5,
            }]
        },
        options: {
            responsive: true,
            animation: false,
            plugins: { legend: { display: false }, tooltip: { enabled: false } },
            scales: { x: { display: false }, y: { display: false } }
        }
    });
}

// ---- MARKET ANALYSIS CHART ----
function renderMarketChart(canvasId, data) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !data || data.length === 0) return;

    const labels = data.map(d => d.date);
    const minPrices = data.map(d => d.min_price);
    const avgPrices = data.map(d => d.avg_price);
    const maxPrices = data.map(d => d.max_price);
    const countData = data.map(d => d.count);

    new Chart(canvas, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'H\u00f6chstpreis',
                    data: maxPrices,
                    borderColor: 'rgba(180, 74, 62, 0.5)',
                    backgroundColor: 'rgba(180, 74, 62, 0.07)',
                    fill: '+1',
                    tension: 0.4,
                    pointRadius: 0,
                    borderWidth: 1.5,
                    borderDash: [5, 4],
                },
                {
                    label: 'Durchschnitt',
                    data: avgPrices,
                    borderColor: '#CD9B77',
                    backgroundColor: 'rgba(205, 155, 119, 0.12)',
                    fill: '+1',
                    tension: 0.4,
                    pointRadius: 3,
                    pointBackgroundColor: '#CD9B77',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    borderWidth: 2.5,
                },
                {
                    label: 'Tiefstpreis',
                    data: minPrices,
                    borderColor: 'rgba(74, 124, 89, 0.5)',
                    backgroundColor: 'rgba(74, 124, 89, 0.07)',
                    fill: false,
                    tension: 0.4,
                    pointRadius: 0,
                    borderWidth: 1.5,
                    borderDash: [5, 4],
                },
            ]
        },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        font: { family: 'Inter', size: 12 },
                        color: '#5E5A59',
                        boxWidth: 14,
                        padding: 18,
                        usePointStyle: true,
                    }
                },
                tooltip: {
                    backgroundColor: '#111111',
                    titleColor: '#CD9B77',
                    bodyColor: '#E6E2E1',
                    padding: 14,
                    cornerRadius: 0,
                    callbacks: {
                        afterTitle: (items) => {
                            const idx = items[0].dataIndex;
                            return countData[idx] + ' Inserate';
                        },
                        label: ctx => ' ' + ctx.dataset.label + ':  ' + Math.round(ctx.parsed.y).toLocaleString('de-DE') + ' \u20AC'
                    }
                }
            },
            scales: {
                y: {
                    grid: { color: '#E6E2E1' },
                    ticks: {
                        font: { family: 'Inter', size: 11 },
                        color: '#5E5A59',
                        callback: v => v.toLocaleString('de-DE') + ' \u20AC'
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: {
                        font: { family: 'Inter', size: 11 },
                        color: '#5E5A59',
                        maxTicksLimit: 14,
                        maxRotation: 0
                    }
                }
            }
        }
    });
}

// ---- BRAND BAR CHART (Top-Marken) ----
function renderBrandChart(canvasId, data) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !data || data.length === 0) return;

    const labels = data.map(d => d.brand);
    const counts = data.map(d => d.count);
    const avgPrices = data.map(d => d.avg_price);

    new Chart(canvas, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Inserate',
                data: counts,
                backgroundColor: 'rgba(205,155,119,0.7)',
                borderColor: '#CD9B77',
                borderWidth: 1,
                borderRadius: 2,
                yAxisID: 'y',
            }, {
                label: '\u00D8 Preis',
                data: avgPrices,
                type: 'line',
                borderColor: '#111111',
                backgroundColor: 'transparent',
                borderWidth: 2,
                pointRadius: 3,
                pointBackgroundColor: '#111111',
                tension: 0.3,
                yAxisID: 'y2',
            }]
        },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: true, position: 'top',
                    labels: { font: { family: 'Inter', size: 11 }, color: '#5E5A59', boxWidth: 12, padding: 14 } },
                tooltip: {
                    backgroundColor: '#111',
                    titleColor: '#CD9B77',
                    bodyColor: '#E6E2E1',
                    padding: 12,
                    callbacks: {
                        label: ctx => ctx.datasetIndex === 0
                            ? ' ' + ctx.parsed.y + ' Inserate'
                            : ' \u00D8 ' + Math.round(ctx.parsed.y).toLocaleString('de-DE') + ' \u20AC'
                    }
                }
            },
            scales: {
                y: {
                    position: 'left',
                    grid: { color: '#E6E2E1' },
                    ticks: { font: { family: 'Inter', size: 11 }, color: '#5E5A59' }
                },
                y2: {
                    position: 'right',
                    grid: { display: false },
                    ticks: {
                        font: { family: 'Inter', size: 11 }, color: '#5E5A59',
                        callback: v => v.toLocaleString('de-DE') + ' \u20AC'
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: { font: { family: 'Inter', size: 11 }, color: '#5E5A59', maxRotation: 30 }
                }
            }
        }
    });
}

// ---- FUEL DONUT CHART (Kraftstoffverteilung) ----
function renderFuelChart(canvasId, data) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !data || data.length === 0) return;

    const colors = ['#CD9B77','#111111','#4A7C59','#B44A3E','#7B5EA7','#00B2A9','#E6C97A','#5E5A59'];

    new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: data.map(d => d.fuel),
            datasets: [{
                data: data.map(d => d.count),
                backgroundColor: colors.slice(0, data.length),
                borderColor: '#FAF7F4',
                borderWidth: 3,
            }]
        },
        options: {
            responsive: true,
            cutout: '62%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { font: { family: 'Inter', size: 11 }, color: '#5E5A59', padding: 14, boxWidth: 12 }
                },
                tooltip: {
                    backgroundColor: '#111',
                    bodyColor: '#E6E2E1',
                    padding: 12,
                    callbacks: { label: ctx => ' ' + ctx.label + ': ' + ctx.parsed.toLocaleString('de-DE') + ' Inserate' }
                }
            }
        }
    });
}

// ---- SEGMENT BAR CHART (Preissegmente) ----
function renderSegmentChart(canvasId, data) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !data || data.length === 0) return;

    const segColors = ['#4A7C59','#CD9B77','#B44A3E','#7B5EA7'];

    new Chart(canvas, {
        type: 'bar',
        data: {
            labels: data.map(d => d.segment),
            datasets: [{
                label: 'Inserate',
                data: data.map(d => d.count),
                backgroundColor: segColors,
                borderWidth: 0,
                borderRadius: 2,
            }]
        },
        options: {
            responsive: true,
            indexAxis: 'y',
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#111',
                    bodyColor: '#fff',
                    callbacks: { label: ctx => ' ' + ctx.parsed.x.toLocaleString('de-DE') + ' Inserate' }
                }
            },
            scales: {
                x: { grid: { color: '#E6E2E1' }, ticks: { font: { family: 'Inter', size: 11 }, color: '#5E5A59' } },
                y: { grid: { display: false }, ticks: { font: { family: 'Inter', size: 12 }, color: '#111111' } }
            }
        }
    });
}

// ---- PLATFORM PIE CHART (Plattform-Aufteilung) ----
function renderPlatformChart(canvasId, data) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !data || data.length === 0) return;

    const platformColors = {
        'mobile_de': '#F0C94D', 'autoscout24': '#FF6B35', 'kleinanzeigen': '#4A7C59',
        'pkw_de': '#7B5EA7', 'autohero': '#1A1A2E', 'heycar': '#00B2A9',
    };
    const platformNames = {
        'mobile_de': 'Mobile.de', 'autoscout24': 'AutoScout24', 'kleinanzeigen': 'Kleinanzeigen',
        'pkw_de': 'pkw.de', 'autohero': 'Autohero', 'heycar': 'heycar',
    };

    new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: data.map(d => platformNames[d.platform] || d.platform),
            datasets: [{
                data: data.map(d => d.count),
                backgroundColor: data.map(d => platformColors[d.platform] || '#999'),
                borderColor: '#FAF7F4',
                borderWidth: 3,
            }]
        },
        options: {
            responsive: true,
            cutout: '62%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { font: { family: 'Inter', size: 11 }, color: '#5E5A59', padding: 14, boxWidth: 12 }
                },
                tooltip: {
                    backgroundColor: '#111',
                    bodyColor: '#E6E2E1',
                    padding: 12,
                    callbacks: { label: ctx => ' ' + ctx.label + ': ' + ctx.parsed.toLocaleString('de-DE') }
                }
            }
        }
    });
}

// ---- VOLUME BAR CHART (Inserate pro Tag) ----
function renderVolumeChart(canvasId, data) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !data || data.length === 0) return;

    new Chart(canvas, {
        type: 'bar',
        data: {
            labels: data.map(d => d.date),
            datasets: [{
                label: 'Inserate',
                data: data.map(d => d.count),
                backgroundColor: 'rgba(205, 155, 119, 0.5)',
                borderColor: '#CD9B77',
                borderWidth: 1,
                borderRadius: 0,
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#111',
                    bodyColor: '#fff',
                    callbacks: { label: ctx => ctx.parsed.y + ' Inserate' }
                }
            },
            scales: {
                y: {
                    grid: { color: '#E6E2E1' },
                    ticks: { font: { family: 'Inter', size: 11 }, color: '#5E5A59' }
                },
                x: {
                    grid: { display: false },
                    ticks: { font: { family: 'Inter', size: 10 }, color: '#5E5A59', maxTicksLimit: 14, maxRotation: 0 }
                }
            }
        }
    });
}
