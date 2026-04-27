/**
 * Greek Fuel Prices — frontend.
 * Talks to the PHP API at api/v1/. Renders a time-series line chart.
 *
 * The user can select multiple fuels and/or multiple prefectures;
 * one line is drawn per (prefecture × fuel) combination.
 */

const GREEK_MONTHS = ['Ιαν', 'Φεβ', 'Μαρ', 'Απρ', 'Μάι', 'Ιουν', 'Ιουλ', 'Αυγ', 'Σεπ', 'Οκτ', 'Νοε', 'Δεκ'];

const DEFAULT_FUEL = 'Αμόλυβδη 95';
const DEFAULT_PREFECTURE = 'ΠΑΝΕΛΛΗΝΙΟΣ ΣΤΑΘΜΙΣΜΕΝΟΣ Μ.Ο.';
const NATIONAL_LABEL = 'Όλη η Ελλάδα';

// Distinct line colors. Cycles if the user picks more series than colors.
const PALETTE = [
    '#22c55e', // green
    '#0f1b3e', // navy
    '#60a5fa', // blue
    '#f59e0b', // amber
    '#e11d48', // rose
    '#8b5cf6', // purple
    '#06b6d4', // cyan
    '#ec4899', // pink
];

let chart = null;
let coverageLatest = null;
let fuelPicker = null;
let prefecturePicker = null;
let fetchToken = 0;

const els = {
    fuelRoot: document.getElementById('fuel-select'),
    prefectureRoot: document.getElementById('prefecture-select'),
    chips: document.getElementById('range-chips'),
    status: document.getElementById('chart-status'),
    canvas: document.getElementById('price-chart'),
    latestGrid: document.getElementById('latest-grid'),
    latestSubtitle: document.getElementById('latest-subtitle'),
};

// Fuel display order for the headline cards (by fuel-types ID).
// 5 = Diesel Θέρμανσης Κατ΄ οίκον is intentionally excluded — it's seasonal.
const HEADLINE_FUEL_IDS = [1, 2, 3, 4];
const FUEL_COLORS_BY_ID = {
    1: '#22c55e', // Αμόλυβδη 95 οκτ.
    2: '#f59e0b', // Αμόλυβδη 100 οκτ.
    3: '#0f1b3e', // Diesel Κίνησης
    4: '#60a5fa', // Υγραέριο κίνησης (Autogas)
};

// ---- API ----------------------------------------------------------------

async function apiGet(path, params = {}) {
    const qs = new URLSearchParams(params).toString();
    const url = `api/v1/${path}${qs ? '?' + qs : ''}`;
    const res = await fetch(url, { headers: { 'Accept': 'application/json' } });
    const body = await res.json();
    if (!res.ok || body.error) {
        throw new Error(body?.error?.message || `HTTP ${res.status}`);
    }
    return body;
}

// ---- MultiSelect --------------------------------------------------------

class MultiSelect {
    constructor(root, items, { defaultIds = [], placeholder = 'Επιλέξτε...', countLabel = 'επιλογές' } = {}) {
        this.root = root;
        this.trigger = root.querySelector('.multi-select-trigger');
        this.label = root.querySelector('.trigger-label');
        this.panel = root.querySelector('.multi-select-panel');
        this.items = items;
        this.selected = new Set(defaultIds);
        this.placeholder = placeholder;
        this.countLabel = countLabel;
        this.changeListeners = [];

        this.renderOptions();
        this.refreshLabel();
        this.bindEvents();
    }

    renderOptions() {
        this.panel.innerHTML = '';
        for (const item of this.items) {
            const row = document.createElement('label');
            row.className = 'multi-option';
            if (this.selected.has(item.id)) row.classList.add('is-selected');

            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.checked = this.selected.has(item.id);
            cb.addEventListener('change', () => this.toggle(item.id, cb.checked, row));

            const span = document.createElement('span');
            span.textContent = item.name;

            row.append(cb, span);
            this.panel.appendChild(row);
        }
    }

    toggle(id, on, row) {
        if (on) this.selected.add(id);
        else this.selected.delete(id);
        row.classList.toggle('is-selected', on);
        this.refreshLabel();
        this.changeListeners.forEach(fn => fn());
    }

    refreshLabel() {
        const n = this.selected.size;
        if (n === 0) {
            this.label.textContent = this.placeholder;
        } else if (n === 1) {
            const id = [...this.selected][0];
            const item = this.items.find(i => i.id === id);
            this.label.textContent = item ? item.name : this.placeholder;
        } else {
            this.label.textContent = `${n} ${this.countLabel}`;
        }
    }

    bindEvents() {
        this.trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            const open = !this.panel.hasAttribute('hidden') ? false : true;
            this.setOpen(open);
        });

        document.addEventListener('click', (e) => {
            if (!this.root.contains(e.target)) this.setOpen(false);
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.setOpen(false);
        });
    }

    setOpen(open) {
        if (open) {
            this.panel.removeAttribute('hidden');
            this.root.classList.add('is-open');
            this.trigger.setAttribute('aria-expanded', 'true');
        } else {
            this.panel.setAttribute('hidden', '');
            this.root.classList.remove('is-open');
            this.trigger.setAttribute('aria-expanded', 'false');
        }
    }

    onChange(fn) { this.changeListeners.push(fn); }

    getSelectedItems() {
        return this.items.filter(i => this.selected.has(i.id));
    }
}

// ---- Latest prices cards ------------------------------------------------

async function loadLatestPrices(fuels) {
    try {
        const res = await apiGet('prices/latest');
        const national = res.data.entries.find(e => e.prefecture.name === DEFAULT_PREFECTURE);
        if (!national) return;

        els.latestSubtitle.textContent = `${formatGreekDate(res.data.date)}`;
        els.latestGrid.innerHTML = '';

        for (const fuelId of HEADLINE_FUEL_IDS) {
            const fuel = fuels.find(f => f.id === fuelId);
            if (!fuel) continue;
            const price = national.prices[fuel.name];
            if (price == null) continue;
            els.latestGrid.appendChild(buildLatestCard(fuel.name, price));
        }
    } catch (e) {
        console.error('Latest prices failed:', e);
    }
}

function buildLatestCard(fuelName, price) {
    const card = document.createElement('div');
    card.className = 'latest-card';

    const name = document.createElement('div');
    name.className = 'latest-card-name';
    name.textContent = fuelName;

    const priceEl = document.createElement('div');
    priceEl.className = 'latest-card-price';
    priceEl.textContent = price.toFixed(3);

    const unit = document.createElement('span');
    unit.className = 'latest-card-unit';
    unit.textContent = '€/L';
    priceEl.appendChild(unit);

    card.append(name, priceEl);
    return card;
}

// ---- Status -------------------------------------------------------------

function showStatus(text, kind = 'info') {
    els.status.textContent = text;
    els.status.dataset.kind = kind;
    els.status.hidden = false;
}

function hideStatus() {
    els.status.hidden = true;
}

// ---- Range chips --------------------------------------------------------

function computeRange(rangeKey, latestDate) {
    const to = latestDate ? new Date(latestDate) : new Date();
    let from;

    if (rangeKey === 'ALL') {
        from = new Date('2017-01-01');
    } else {
        from = new Date(to);
        const months = { '1M': 1, '3M': 3, '6M': 6, '1Y': 12 }[rangeKey] ?? 12;
        from.setMonth(from.getMonth() - months);
    }

    return { from: iso(from), to: iso(to) };
}

function iso(d) {
    return d.toISOString().slice(0, 10);
}

function activeRange() {
    const active = els.chips.querySelector('.chip.is-active');
    return active ? active.dataset.range : 'ALL';
}

// ---- Chart --------------------------------------------------------------

function buildChart() {
    const ctx = els.canvas.getContext('2d');

    chart = new Chart(ctx, {
        type: 'line',
        data: { labels: [], datasets: [] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: '#374151',
                        font: { family: 'Commissioner', size: 13, weight: '500' },
                        usePointStyle: true,
                        pointStyle: 'circle',
                        boxWidth: 8,
                        boxHeight: 8,
                        padding: 14,
                    },
                },
                tooltip: {
                    backgroundColor: '#0f1b3e',
                    titleFont: { family: 'Commissioner', size: 13, weight: '600' },
                    bodyFont: { family: 'Commissioner', size: 13 },
                    padding: 12,
                    callbacks: {
                        title: (items) => formatGreekDate(items[0].parsed.x),
                        label: (item) => `${item.dataset.label}: ${item.parsed.y.toFixed(3)} €/L`,
                    },
                },
            },
            scales: {
                x: {
                    type: 'time',
                    time: { unit: 'month' },
                    ticks: {
                        color: '#6b7280',
                        font: { family: 'Commissioner', size: 12 },
                        maxRotation: 0,
                        autoSkip: true,
                        callback: (value) => GREEK_MONTHS[new Date(value).getMonth()],
                    },
                    grid: { display: false },
                    border: { color: '#e5e7eb' },
                },
                y: {
                    ticks: {
                        color: '#6b7280',
                        font: { family: 'Commissioner', size: 12 },
                        callback: (v) => v.toFixed(3) + '€',
                    },
                    grid: { color: '#f1f5f9' },
                    border: { display: false },
                },
            },
        },
    });
}

function formatGreekDate(ts) {
    const d = new Date(ts);
    return `${d.getDate()} ${GREEK_MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

function makeDataset(label, color, points, fill) {
    return {
        label,
        data: points,
        borderColor: color,
        backgroundColor: fill ? hexToRgba(color, 0.18) : color,
        borderWidth: 2.2,
        pointRadius: 0,
        pointHoverRadius: 5,
        pointHoverBackgroundColor: color,
        pointHoverBorderColor: '#fff',
        pointHoverBorderWidth: 2,
        fill,
        tension: 0.25,
    };
}

function hexToRgba(hex, alpha) {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

// ---- Load + render ------------------------------------------------------

async function refreshChart() {
    const fuels = fuelPicker.getSelectedItems();
    const prefectures = prefecturePicker.getSelectedItems();

    if (fuels.length === 0 || prefectures.length === 0) {
        showStatus('Επιλέξτε τουλάχιστον ένα καύσιμο και μία περιοχή.');
        chart.data.datasets = [];
        chart.update();
        return;
    }

    const { from, to } = computeRange(activeRange(), coverageLatest);
    const combos = [];
    for (const p of prefectures) {
        for (const f of fuels) combos.push({ prefecture: p, fuel: f });
    }

    showStatus('Φόρτωση…');
    const myToken = ++fetchToken;

    try {
        const responses = await Promise.all(combos.map(({ prefecture, fuel }) =>
            apiGet('prices', {
                prefecture_id: prefecture.id,
                fuel_type_id: fuel.id,
                from,
                to,
            }).then(r => ({ prefecture, fuel, points: r.data }))
        ));

        // Discard if a newer fetch superseded us mid-flight.
        if (myToken !== fetchToken) return;

        const fillUnderLine = responses.length === 1;

        const datasets = responses.map((r, i) => {
            const color = PALETTE[i % PALETTE.length];
            const label = combos.length === 1
                ? `${r.fuel.name} — ${r.prefecture.name}`
                : (prefectures.length === 1 ? r.fuel.name
                  : fuels.length === 1 ? r.prefecture.name
                  : `${r.fuel.name} — ${r.prefecture.name}`);
            const points = r.points.map(p => ({ x: p.date, y: p.price }));
            return makeDataset(label, color, points, fillUnderLine);
        });

        const empty = datasets.every(ds => ds.data.length === 0);
        if (empty) {
            showStatus('Δεν βρέθηκαν δεδομένα για την επιλογή σας.');
            chart.data.datasets = [];
            chart.update();
            return;
        }

        hideStatus();
        chart.data.datasets = datasets;
        chart.update();
    } catch (e) {
        if (myToken !== fetchToken) return;
        console.error(e);
        showStatus(`Σφάλμα: ${e.message}`, 'error');
    }
}

// ---- Init ---------------------------------------------------------------

async function init() {
    buildChart();
    showStatus('Φόρτωση…');

    let prefectures, fuels, root;
    try {
        [root, prefectures, fuels] = await Promise.all([
            apiGet(''),
            apiGet('prefectures'),
            apiGet('fuel-types'),
        ]);
    } catch (e) {
        console.error(e);
        showStatus(`Αδυναμία σύνδεσης με το API: ${e.message}`, 'error');
        return;
    }

    coverageLatest = root.data?.data_coverage?.latest || null;

    // Float national average to the top, rename for the picker.
    const nationalRow = prefectures.data.find(p => p.name === DEFAULT_PREFECTURE);
    const prefectureItems = prefectures.data
        .map(p => ({ id: p.id, name: p.name === DEFAULT_PREFECTURE ? NATIONAL_LABEL : p.name }))
        .sort((a, b) => (a.id === nationalRow?.id ? -1 : b.id === nationalRow?.id ? 1 : 0));

    const defaultFuel = fuels.data.find(f => f.name === DEFAULT_FUEL) || fuels.data[0];

    fuelPicker = new MultiSelect(els.fuelRoot, fuels.data, {
        defaultIds: defaultFuel ? [defaultFuel.id] : [],
    });
    prefecturePicker = new MultiSelect(els.prefectureRoot, prefectureItems, {
        defaultIds: nationalRow ? [nationalRow.id] : [],
    });

    fuelPicker.onChange(refreshChart);
    prefecturePicker.onChange(refreshChart);

    els.chips.addEventListener('click', (e) => {
        const btn = e.target.closest('.chip');
        if (!btn) return;
        els.chips.querySelectorAll('.chip').forEach(c => c.classList.remove('is-active'));
        btn.classList.add('is-active');
        refreshChart();
    });

    refreshChart();
    loadLatestPrices(fuels.data);
}

init();
