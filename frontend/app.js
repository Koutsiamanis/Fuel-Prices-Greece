/**
 * Greek Fuel Prices — frontend.
 * Talks to the PHP API at ../api/v1/. Renders a time-series line chart.
 */

const GREEK_MONTHS = ['Ιαν', 'Φεβ', 'Μαρ', 'Απρ', 'Μάι', 'Ιουν', 'Ιουλ', 'Αυγ', 'Σεπ', 'Οκτ', 'Νοε', 'Δεκ'];

const DEFAULT_FUEL = 'Αμόλυβδη 95';
const DEFAULT_PREFECTURE = 'ΠΑΝΕΛΛΗΝΙΟΣ ΣΤΑΘΜΙΣΜΕΝΟΣ Μ.Ο.';
const NATIONAL_LABEL = 'Όλη η Ελλάδα';

let chart = null;
let coverageLatest = null;

const els = {
    fuel: document.getElementById('fuel-select'),
    prefecture: document.getElementById('prefecture-select'),
    chips: document.getElementById('range-chips'),
    status: document.getElementById('chart-status'),
    canvas: document.getElementById('price-chart'),
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

// ---- Status -------------------------------------------------------------

function showStatus(text, kind = 'info') {
    els.status.textContent = text;
    els.status.dataset.kind = kind;
    els.status.hidden = false;
}

function hideStatus() {
    els.status.hidden = true;
}

// ---- Dropdowns ----------------------------------------------------------

function populateSelect(select, items, { labelFor, defaultId }) {
    select.innerHTML = '';
    for (const item of items) {
        const opt = document.createElement('option');
        opt.value = item.id;
        opt.textContent = labelFor(item);
        if (item.id === defaultId) opt.selected = true;
        select.appendChild(opt);
    }
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
    const gradient = ctx.createLinearGradient(0, 0, 0, 420);
    gradient.addColorStop(0, 'rgba(34, 197, 94, 0.25)');
    gradient.addColorStop(1, 'rgba(34, 197, 94, 0)');

    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: '',
                data: [],
                borderColor: '#22c55e',
                backgroundColor: gradient,
                borderWidth: 2.5,
                pointRadius: 0,
                pointHoverRadius: 5,
                pointHoverBackgroundColor: '#22c55e',
                pointHoverBorderColor: '#fff',
                pointHoverBorderWidth: 2,
                fill: true,
                tension: 0.25,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#0f1b3e',
                    titleFont: { family: 'Commissioner', size: 13, weight: '600' },
                    bodyFont: { family: 'Commissioner', size: 13 },
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        title: (items) => formatGreekDate(items[0].parsed.x),
                        label: (item) => `${item.parsed.y.toFixed(3)} €/L`,
                    },
                },
            },
            scales: {
                x: {
                    type: 'time',
                    time: { unit: 'month' },
                    adapters: {},
                    ticks: {
                        color: '#6b7280',
                        font: { family: 'Commissioner', size: 12 },
                        maxRotation: 0,
                        autoSkip: true,
                        callback: (value) => {
                            const d = new Date(value);
                            return GREEK_MONTHS[d.getMonth()];
                        },
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

// ---- Load + render ------------------------------------------------------

async function refreshChart() {
    const prefectureId = Number(els.prefecture.value);
    const fuelTypeId = Number(els.fuel.value);
    if (!prefectureId || !fuelTypeId) return;

    const { from, to } = computeRange(activeRange(), coverageLatest);

    showStatus('Φόρτωση…');

    try {
        const res = await apiGet('prices', {
            prefecture_id: prefectureId,
            fuel_type_id: fuelTypeId,
            from,
            to,
        });

        const points = res.data.map(p => ({ x: p.date, y: p.price }));

        if (points.length === 0) {
            showStatus('Δεν βρέθηκαν δεδομένα για την επιλογή σας.', 'info');
            chart.data.labels = [];
            chart.data.datasets[0].data = [];
            chart.update();
            return;
        }

        hideStatus();
        chart.data.datasets[0].label = res.meta.fuel_type.name;
        chart.data.datasets[0].data = points;
        chart.update();
    } catch (e) {
        console.error(e);
        showStatus(`Σφάλμα: ${e.message}`, 'error');
    }
}

// ---- Init ---------------------------------------------------------------

async function init() {
    buildChart();
    showStatus('Φόρτωση…');

    try {
        const [root, prefectures, fuels] = await Promise.all([
            apiGet(''),
            apiGet('prefectures'),
            apiGet('fuel-types'),
        ]);

        coverageLatest = root.data?.data_coverage?.latest || null;

        const nationalRow = prefectures.data.find(p => p.name === DEFAULT_PREFECTURE);
        const prefectureItems = prefectures.data.map(p => ({
            id: p.id,
            name: p.name === DEFAULT_PREFECTURE ? NATIONAL_LABEL : p.name,
        }));
        // Float national average to the top of the list for easy access.
        if (nationalRow) {
            prefectureItems.sort((a, b) => (a.id === nationalRow.id ? -1 : b.id === nationalRow.id ? 1 : 0));
        }

        populateSelect(els.prefecture, prefectureItems, {
            labelFor: p => p.name,
            defaultId: nationalRow?.id,
        });

        const defaultFuel = fuels.data.find(f => f.name === DEFAULT_FUEL) || fuels.data[0];
        populateSelect(els.fuel, fuels.data, {
            labelFor: f => f.name,
            defaultId: defaultFuel?.id,
        });
    } catch (e) {
        console.error(e);
        showStatus(`Αδυναμία σύνδεσης με το API: ${e.message}`, 'error');
        return;
    }

    els.fuel.addEventListener('change', refreshChart);
    els.prefecture.addEventListener('change', refreshChart);
    els.chips.addEventListener('click', (e) => {
        const btn = e.target.closest('.chip');
        if (!btn) return;
        els.chips.querySelectorAll('.chip').forEach(c => c.classList.remove('is-active'));
        btn.classList.add('is-active');
        refreshChart();
    });

    refreshChart();
}

init();
