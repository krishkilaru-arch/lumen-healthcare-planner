// Lumen Healthcare Planner - Frontend Logic
// ===========================================

let currentPage = 'dashboard';
let desertMap = null;
let statesCache = null;

// --- Utility ---
function showLoading(id) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = '<div class="flex items-center justify-center py-12"><div class="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-red"></div><span class="ml-3 text-gray-500">Loading...</span></div>';
}

async function loadStates() {
    if (statesCache) return statesCache;
    try {
        const res = await fetch('/api/filters/states');
        const data = await res.json();
        statesCache = data.states || [];
    } catch(e) { statesCache = []; }
    return statesCache;
}

async function loadCitiesForStates(states, citySelectId, capability, procedure) {
    const sel = document.getElementById(citySelectId);
    if (!states.length) { sel.innerHTML = '<option value="">Select state first</option>'; return; }
    sel.innerHTML = '<option value="">Loading cities...</option>';
    const params = new URLSearchParams({ state: states.join(',') });
    if (capability) params.set('capability', capability);
    if (procedure)  params.set('procedure',  procedure);
    const res = await fetch('/api/filters/cities?' + params);
    const data = await res.json();
    const cities = data.cities || [];
    sel.innerHTML = '<option value="">All cities (' + cities.length + ')</option>' +
        cities.map(c => '<option value="' + c.name + '">' + c.name + ' (' + c.count + ')</option>').join('');
}

// --- Multi-Select Dropdown Component ---
function createMultiSelect(containerId, items, placeholder, onChange) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const selected = new Set();
    container.innerHTML =
        '<div class="multi-select-wrapper relative">' +
            '<button type="button" class="multi-select-btn border rounded-lg px-3 py-2 text-sm w-full text-left bg-white flex justify-between items-center" onclick="this.nextElementSibling.classList.toggle(\'hidden\')">' +
                '<span class="multi-select-label text-gray-500">' + placeholder + '</span>' +
                '<svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>' +
            '</button>' +
            '<div class="multi-select-dropdown hidden absolute z-50 mt-1 w-full bg-white border rounded-lg shadow-lg max-h-60 overflow-y-auto">' +
                '<div class="p-2 border-b"><input type="text" placeholder="Search..." class="w-full border rounded px-2 py-1 text-sm" oninput="filterMultiOptions(this)"></div>' +
                '<div class="multi-select-options">' +
                    items.map(i =>
                        '<label class="flex items-center gap-2 px-3 py-1.5 hover:bg-gray-50 cursor-pointer text-sm multi-option" data-value="' + i.value + '" data-search="' + i.name.toLowerCase() + '">' +
                            '<input type="checkbox" value="' + i.value + '" class="rounded border-gray-300">' +
                            '<span class="flex-1">' + i.name + '</span>' +
                            '<span class="text-gray-400 text-xs">' + i.count + '</span>' +
                        '</label>'
                    ).join('') +
                '</div>' +
            '</div>' +
        '</div>';
    container.querySelectorAll('input[type="checkbox"]').forEach(cb => {
        cb.addEventListener('change', () => {
            if (cb.checked) selected.add(cb.value);
            else selected.delete(cb.value);
            const label = container.querySelector('.multi-select-label');
            if (selected.size === 0) {
                label.textContent = placeholder;
                label.className = 'multi-select-label text-gray-500';
            } else {
                const names = items.filter(i => selected.has(i.value)).map(i => i.name);
                label.textContent = names.length <= 2 ? names.join(', ') : names.length + ' selected';
                label.className = 'multi-select-label text-brand-dark font-medium';
            }
            if (onChange) onChange(Array.from(selected));
        });
    });
    document.addEventListener('click', (e) => {
        if (!container.contains(e.target)) {
            const dd = container.querySelector('.multi-select-dropdown');
            if (dd) dd.classList.add('hidden');
        }
    });
    container.getSelected = () => Array.from(selected);
    return container;
}

function filterMultiOptions(input) {
    const term = input.value.toLowerCase();
    const options = input.closest('.multi-select-dropdown').querySelectorAll('.multi-option');
    options.forEach(opt => { opt.style.display = opt.dataset.search.includes(term) ? '' : 'none'; });
}

function populateSelect(selId, items, placeholder) {
    const sel = document.getElementById(selId);
    if (!sel) return;
    sel.innerHTML = '<option value="">' + placeholder + '</option>' +
        items.map(i => '<option value="' + (i.value || i.name) + '">' + i.name + (i.count ? ' (' + i.count + ')' : '') + '</option>').join('');
}

// --- Navigation ---
function showPage(page) {
    document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'));
    document.getElementById('page-' + page).classList.remove('hidden');
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.querySelector('[data-page="' + page + '"]').classList.add('active');
    currentPage = page;
    if (page === 'dashboard') loadOverview();
    if (page === 'trust') initTrustFilters();
    if (page === 'deserts') initDesertFilters();
    if (page === 'referral') initReferralFilters();
    if (page === 'readiness') loadReadiness();
}

// --- Dashboard ---
async function loadOverview() {
    showLoading('stats-grid');
    try {
        const res = await fetch('/api/overview');
        const data = await res.json();
        document.getElementById('stats-grid').innerHTML =
            '<div class="stat-card"><div class="value">' + (data.total_facilities || 0).toLocaleString() + '</div><div class="label">Healthcare Facilities</div></div>' +
            '<div class="stat-card"><div class="value">' + (data.total_states || 36) + '</div><div class="label">States & UTs</div></div>' +
            '<div class="stat-card"><div class="value">' + (data.total_districts || 749) + '</div><div class="label">Districts</div></div>' +
            '<div class="stat-card"><div class="value">' + (data.total_specialties || 0).toLocaleString() + '</div><div class="label">Medical Specialties</div></div>';
    } catch(e) { console.error('Overview load failed:', e); }
}

// --- Trust Desk ---
let trustSelectedStates = [];
let trustSelectedCaps  = [];
let trustCapInitDone   = false;

async function refreshTrustStates() {
    const cap = trustSelectedCaps.length === 1 ? trustSelectedCaps[0] : '';
    const url  = '/api/filters/states' + (cap ? '?capability=' + encodeURIComponent(cap) : '');
    let states = [];
    try {
        const res  = await fetch(url);
        const data = await res.json();
        states = data.states || [];
    } catch(e) { states = []; }
    trustSelectedStates = [];
    createMultiSelect('trust-state-ms', states, 'Select state(s)...', async (selected) => {
        trustSelectedStates = selected;
        await refreshTrustDistricts();
    });
    const distSel = document.getElementById('trust-district');
    if (distSel) distSel.innerHTML = '<option value="">All districts</option>';
}

async function refreshTrustDistricts() {
    const distSel = document.getElementById('trust-district');
    if (!distSel) return;
    const states = trustSelectedStates;
    const cap    = trustSelectedCaps.length === 1 ? trustSelectedCaps[0] : '';
    if (!states.length) {
        distSel.innerHTML = '<option value="">Select state first</option>';
        return;
    }
    distSel.innerHTML = '<option value="">Loading...</option>';
    const params = new URLSearchParams({ state: states.join(',') });
    if (cap) params.set('capability', cap);
    try {
        const res   = await fetch('/api/filters/districts?' + params);
        const data  = await res.json();
        const dists = data.districts || [];
        distSel.innerHTML =
            '<option value="">All districts (' + dists.length + ')</option>' +
            dists.map(d =>
                '<option value="' + d.value + '">' + d.name + ' (' + d.count + ')</option>'
            ).join('');
    } catch(e) {
        distSel.innerHTML = '<option value="">All districts</option>';
    }
}

async function initTrustFilters() {
    if (trustCapInitDone) return;
    let caps = [];
    try {
        const res  = await fetch('/api/trust/capabilities');
        const data = await res.json();
        caps = (data.capabilities || []).map(c => ({ name: c, value: c, count: '' }));
    } catch(e) {
        caps = ['ICU','Maternity','Emergency','Oncology','Trauma','NICU',
                'Dialysis','Cardiology','Orthopedics','Neurology','Pediatrics',
                'Ophthalmology','Radiology','Pathology','Physiotherapy'
               ].map(c => ({ name: c, value: c, count: '' }));
    }
    createMultiSelect('trust-capability-ms', caps, 'Select capability...', async (selected) => {
        trustSelectedCaps = selected;
        await refreshTrustStates();
    });
    await refreshTrustStates();
    trustCapInitDone = true;
}

async function loadTrust() {
    const capabilities = trustSelectedCaps;
    const states = trustSelectedStates;
    const district = document.getElementById('trust-district') ? document.getElementById('trust-district').value : '';
    const city = district;
    const minScore = parseFloat(document.getElementById('trust-min') ? document.getElementById('trust-min').value : '0') / 100;
    const params = new URLSearchParams();
    if (capabilities.length) params.set('capability', capabilities.join(','));
    if (states.length) params.set('state', states.join(','));
    if (city) params.set('city', city);
    if (minScore > 0) params.set('min_score', minScore);
    params.set('limit', '30');

    showLoading('trust-results');
    try {
        const res = await fetch('/api/trust/scores?' + params);
        const data = await res.json();
        const container = document.getElementById('trust-results');
        if (data.error) { container.innerHTML = '<p class="text-red-500 py-4">' + data.error + '</p>'; return; }
        if (!data.facilities || !data.facilities.length) {
            const capNames = capabilities.length ? capabilities.join(', ') : 'selected capabilities';
            const hint = city
                ? 'No facilities claiming <strong>' + capNames + '</strong> found in <strong>' + city + '</strong>. Try removing the city filter.'
                : 'No results found. Try selecting a capability or broader region.';
            container.innerHTML = '<p class="text-gray-500 py-8 text-center">' + hint + '</p>';
            return;
        }
        const capLabel = data.capability ? ' for <strong>' + data.capability + '</strong>' : '';
        container.innerHTML = '<p class="text-xs text-gray-400 mb-2">' + data.total + ' facilities evaluated' + capLabel + '</p>' +
        data.facilities.map(function(f) {
            var signalColors = {strong:'bg-green-100 text-green-800',partial:'bg-yellow-100 text-yellow-800',weak:'bg-orange-100 text-orange-800',no_claim:'bg-gray-100 text-gray-600'};
            var signalLabels = {strong:'Strong Evidence',partial:'Partial Evidence',weak:'Weak/Suspicious',no_claim:'No Claim'};
            var sig = f.capability_signal;
            var sigBadge = sig ? '<span class="text-xs px-2 py-0.5 rounded font-medium ' + (signalColors[sig] || '') + '">' + (signalLabels[sig] || sig) + '</span>' : '';
            var citations = (f.capability_citations || []).map(function(c) {
                return '<div class="text-xs bg-gray-50 rounded p-2 mt-1 border-l-2 border-brand-red"><span class="font-medium text-gray-600">[' + c.field + ']</span> <span class="text-gray-700">"' + c.text + '"</span></div>';
            }).join('');
            return '<div class="bg-white rounded-xl p-4 shadow-sm border hover:shadow-md transition">' +
                '<div class="flex justify-between items-start">' +
                    '<div class="flex-1">' +
                        '<div class="flex items-center gap-2">' +
                            '<h4 class="font-semibold text-brand-dark">' + (f.name || f.facility_id) + '</h4>' +
                            sigBadge +
                        '</div>' +
                        '<p class="text-sm text-gray-500 mt-0.5">' + (f.city || '') + (f.city && f.state ? ', ' : '') + (f.state || '') + '</p>' +
                        (citations ? '<details class="mt-2"><summary class="text-xs text-brand-red cursor-pointer font-medium">View citations (' + f.capability_citations.length + ')</summary><div class="mt-1">' + citations + '</div></details>' : '') +
                        '<div class="mt-2 flex gap-1 flex-wrap">' +
                            (f.evidence || []).slice(0, 3).map(function(e) { return '<span class="evidence-tag">' + e.type + '</span>'; }).join('') +
                        '</div>' +
                    '</div>' +
                    '<div class="text-right ml-4">' +
                        '<div class="text-2xl font-bold ' + (f.overall_score >= 0.7 ? 'text-green-600' : f.overall_score >= 0.4 ? 'text-yellow-600' : 'text-red-600') + '">' +
                            (f.overall_score * 100).toFixed(0) +
                        '</div>' +
                        '<div class="text-xs text-gray-400">trust score</div>' +
                        '<div class="mt-1 grid grid-cols-3 gap-1 text-xs text-gray-500">' +
                            '<span title="Completeness">C:' + (f.completeness*100).toFixed(0) + '</span>' +
                            '<span title="Verification">V:' + (f.verification*100).toFixed(0) + '</span>' +
                            '<span title="Recency">R:' + (f.recency*100).toFixed(0) + '</span>' +
                        '</div>' +
                    '</div>' +
                '</div>' +
            '</div>';
        }).join('');
    } catch(e) { console.error('Trust load failed:', e); }
}

// --- Medical Deserts ---
let desertCapInitDone = false;
let desertSelectedCap = '';

async function refreshDesertStates() {
    const url = '/api/filters/states' + (desertSelectedCap ? '?capability=' + encodeURIComponent(desertSelectedCap) : '');
    let states = [];
    try {
        const res  = await fetch(url);
        const data = await res.json();
        states = data.states || [];
    } catch(e) { states = []; }
    populateSelect('desert-state', states, 'All states (' + states.length + ')');
}

async function initDesertFilters() {
    if (desertCapInitDone) return;
    let caps = [];
    try {
        const res  = await fetch('/api/trust/capabilities');
        const data = await res.json();
        caps = (data.capabilities || []).map(c => ({ name: c, value: c, count: '' }));
    } catch(e) {
        caps = ['ICU','Maternity','Emergency','Oncology','Trauma','NICU',
                'Dialysis','Cardiology','Orthopedics','Neurology','Pediatrics',
                'Ophthalmology','Radiology','Pathology','Physiotherapy'
               ].map(c => ({ name: c, value: c, count: '' }));
    }
    createMultiSelect('desert-capability-ms', caps, 'All capabilities...', async (selected) => {
        desertSelectedCap = selected.length === 1 ? selected[0] : '';
        await refreshDesertStates();
    });
    await refreshDesertStates();
    desertCapInitDone = true;
}

async function loadDeserts() {
    const state     = document.getElementById('desert-state')     ? document.getElementById('desert-state').value     : '';
    const threshold = document.getElementById('desert-threshold') ? document.getElementById('desert-threshold').value : '5';
    const params = new URLSearchParams({ threshold: threshold });
    if (state)             params.set('state',      state);
    if (desertSelectedCap) params.set('capability', desertSelectedCap);
    showLoading('desert-list');
    try {
        const res  = await fetch('/api/deserts/analysis?' + params);
        const data = await res.json();
        _lastDesertData = data;
        const listEl = document.getElementById('desert-list');
        if (data.error) { listEl.innerHTML = '<p class="text-red-500 py-4">' + data.error + '</p>'; return; }

        const s = data.summary || {};
        listEl.innerHTML =
            '<div class="bg-white rounded-lg p-3 border mb-3">' +
              '<div class="grid grid-cols-6 gap-1 text-center text-xs">' +
                '<div><div class="text-lg font-bold text-red-600">'    + (s.critical || 0)       + '</div>Critical</div>' +
                '<div><div class="text-lg font-bold text-orange-500">' + (s.high || 0)           + '</div>High</div>' +
                '<div><div class="text-lg font-bold text-yellow-500">' + (s.moderate || 0)       + '</div>Moderate</div>' +
                '<div><div class="text-lg font-bold text-green-500">'  + (s.low || 0)            + '</div>Low</div>' +
                '<div><div class="text-lg font-bold text-brand-red">'  + (s.confirmed_gaps || 0) + '</div>Confirmed</div>' +
                '<div><div class="text-lg font-bold text-gray-400">'   + (s.data_limited || 0)   + '</div>Data gap?</div>' +
              '</div>' +
              '<div class="mt-2 text-right">' +
                '<button onclick="saveDesertScenario()" class="text-xs text-brand-red border border-brand-red rounded px-2 py-1 hover:bg-red-50">Save Scenario</button>' +
              '</div>' +
            '</div>' +
            (data.deserts || []).slice(0, 80).map(function(d) {
                var sevCls  = {critical:'bg-red-100 text-red-700',high:'bg-orange-100 text-orange-700',moderate:'bg-yellow-100 text-yellow-700',low:'bg-green-100 text-green-700'}[d.severity] || '';
                var confCls = d.confidence === 'confirmed_gap' ? 'bg-red-50 text-red-700 border-red-200'
                            : d.confidence === 'data_limited'  ? 'bg-gray-50 text-gray-500 border-gray-200'
                            : 'bg-yellow-50 text-yellow-700 border-yellow-200';
                var confLbl = d.confidence === 'confirmed_gap' ? 'Confirmed gap'
                            : d.confidence === 'data_limited'  ? 'Data limited'
                            : 'Possible gap';
                var rowId = 'dr-' + (d.district || '').replace(/[^a-z0-9]/gi, '-');
                return '<div class="bg-white rounded-lg border hover:shadow-sm mb-1">' +
                    '<div class="flex justify-between items-center p-3 cursor-pointer" onclick="toggleDesertDrill(\'' + rowId + '\',\'' + encodeURIComponent(d.state || '') + '\',\'' + encodeURIComponent(d.district || '') + '\')">' +
                        '<div>' +
                            '<span class="font-medium text-sm">' + (d.district || 'Unknown') + '</span>' +
                            '<span class="text-xs text-gray-400 ml-2">' + (d.state || '') + '</span>' +
                            '<span class="ml-2 text-xs px-1.5 py-0.5 rounded border ' + confCls + '" title="' + (d.confidence_note || '') + '">' + confLbl + '</span>' +
                        '</div>' +
                        '<div class="flex items-center gap-2">' +
                            '<span class="text-xs px-2 py-0.5 rounded ' + sevCls + '">' + d.severity + '</span>' +
                            '<span class="text-sm font-semibold text-gray-700">' + d.facility_count + ' facilities</span>' +
                            '<svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>' +
                        '</div>' +
                    '</div>' +
                    '<div id="' + rowId + '" class="hidden border-t px-3 pb-3"></div>' +
                '</div>';
            }).join('') +
            '<div id="desert-scenarios" class="mt-4"></div>';

        if (data.deserts && data.deserts.length) initDesertMap(data.deserts);
        loadDesertScenarios();
    } catch(e) { console.error('Deserts load failed:', e); }
}

let _lastDesertData = null;

async function toggleDesertDrill(rowId, stateEnc, districtEnc) {
    const panel = document.getElementById(rowId);
    if (!panel) return;
    if (!panel.classList.contains('hidden')) { panel.classList.add('hidden'); return; }
    panel.classList.remove('hidden');
    panel.innerHTML = '<div class="text-xs text-gray-400 py-2">Loading facilities...</div>';
    const p = new URLSearchParams({ state: decodeURIComponent(stateEnc), district: decodeURIComponent(districtEnc) });
    if (desertSelectedCap) p.set('capability', desertSelectedCap);
    try {
        const res  = await fetch('/api/deserts/facilities?' + p);
        const data = await res.json();
        const facs = data.facilities || [];
        if (!facs.length) { panel.innerHTML = '<p class="text-xs text-gray-400 py-2">No facilities found for these filters.</p>'; return; }
        panel.innerHTML = facs.map(function(f) {
            return '<div class="text-xs border-b py-2 last:border-0">' +
                '<span class="font-medium text-gray-800">' + (f.name || f.unique_id) + '</span>' +
                '<span class="text-gray-400 ml-2 italic">' + (f.organization_type || '') + '</span>' +
                (f.description ? '<p class="text-gray-500 mt-0.5">' + f.description.slice(0, 130) + '\u2026</p>' : '') +
            '</div>';
        }).join('');
    } catch(e) { panel.innerHTML = '<p class="text-xs text-red-400 py-2">Failed to load.</p>'; }
}

async function saveDesertScenario() {
    if (!_lastDesertData) return;
    const name = prompt('Name this scenario:', 'Desert Analysis ' + new Date().toLocaleDateString());
    if (!name) return;
    const state     = document.getElementById('desert-state')     ? document.getElementById('desert-state').value     : '';
    const threshold = document.getElementById('desert-threshold') ? document.getElementById('desert-threshold').value : '5';
    const filters   = JSON.stringify({ capability: desertSelectedCap, state, threshold });
    try {
        const res  = await fetch('/api/deserts/scenarios?' + new URLSearchParams({ name, filters, notes: '' }), { method: 'POST' });
        const data = await res.json();
        if (data.saved) { alert('Scenario saved.'); loadDesertScenarios(); }
        else alert('Save failed: ' + (data.error || ''));
    } catch(e) { alert('Save failed.'); }
}

async function loadDesertScenarios() {
    const el = document.getElementById('desert-scenarios');
    if (!el) return;
    try {
        const res  = await fetch('/api/deserts/scenarios');
        const data = await res.json();
        const rows = data.scenarios || [];
        if (!rows.length) { el.innerHTML = ''; return; }
        el.innerHTML = '<h4 class="text-sm font-semibold text-brand-dark mb-2 mt-2">Saved Scenarios</h4>' +
            rows.map(function(s) {
                var f = {}; try { f = JSON.parse(s.filters_json); } catch(e) {}
                return '<div class="bg-gray-50 rounded p-2 border text-xs flex justify-between items-center mb-1">' +
                    '<div><span class="font-medium">' + s.name + '</span>' +
                    '<span class="text-gray-400 ml-2">' + (f.capability || 'All') + ' \u00b7 ' + (f.state || 'All states') + ' \u00b7 \u2264' + (f.threshold || 5) + ' facilities</span></div>' +
                    '<span class="text-gray-400">' + new Date(s.created_at).toLocaleDateString() + '</span></div>';
            }).join('');
    } catch(e) { /* persist layer unavailable */ }
}

function initDesertMap(deserts) {
    const mapEl = document.getElementById('desert-map');
    if (!mapEl) return;
    if (desertMap) desertMap.remove();
    desertMap = L.map(mapEl).setView([20.5937, 78.9629], 5);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '\u00a9 OpenStreetMap' }).addTo(desertMap);
    var confColors = { confirmed_gap: '#dc2626', possible_gap: '#f97316', data_limited: '#9ca3af' };
    deserts.forEach(function(d) {
        if (d.avg_lat && d.avg_lon) {
            L.circleMarker([d.avg_lat, d.avg_lon], {
                radius: 6, fillColor: confColors[d.confidence] || '#9ca3af',
                color: '#fff', weight: 1, fillOpacity: 0.85
            }).bindPopup(
                '<b>' + (d.district || '') + '</b><br>' + (d.state || '') + '<br>' +
                d.facility_count + ' facilities (' + d.severity + ')<br>' +
                '<em class="text-xs">' + (d.confidence_note || '') + '</em>'
            ).addTo(desertMap);
        }
    });
}

// --- Referral Copilot ---
let referralFiltersReady   = false;
let refSelectedSpecialties = [];
let refSelectedStates      = [];
let _refLat = null;
let _refLon = null;

// Filter 1 (Specialty) → scopes Filter 2 (State) → Filter 2 scopes Filter 3 (City)
async function refreshReferralStates() {
    const cap  = refSelectedSpecialties.join(',');   // all selected caps, OR logic
    const proc = (document.getElementById('ref-procedure') || {}).value || '';
    const qp   = new URLSearchParams();
    if (cap)  qp.set('capability', cap);
    if (proc) qp.set('procedure',  proc.trim());
    const url = '/api/filters/states' + (qp.toString() ? '?' + qp : '');
    let states = [];
    try {
        const res  = await fetch(url);
        const data = await res.json();
        states = data.states || [];
    } catch(e) { states = []; }
    refSelectedStates = [];
    createMultiSelect('ref-state-ms', states, 'Select state(s) (' + states.length + ')...', async (selected) => {
        refSelectedStates = selected;
        await loadCitiesForStates(selected, 'ref-city', cap, proc.trim());  // scoped by specialty+procedure
    });
    const citySel = document.getElementById('ref-city');
    if (citySel) citySel.innerHTML = '<option value="">All cities</option>';
}

async function resolveNearCity() {
    const input  = document.getElementById('ref-near');
    const status = document.getElementById('ref-near-status');
    const city   = input ? input.value.trim() : '';
    if (!city) { _refLat = null; _refLon = null; if (status) status.textContent = ''; return; }
    if (status) status.textContent = '...';
    try {
        const res  = await fetch('/api/referral/locate?city=' + encodeURIComponent(city));
        const data = await res.json();
        if (data.found) {
            _refLat = data.lat;
            _refLon = data.lon;
            if (status) { status.textContent = '✓'; status.className = 'absolute right-2 top-2.5 text-xs text-green-500'; }
        } else {
            _refLat = null; _refLon = null;
            if (status) { status.textContent = '?'; status.className = 'absolute right-2 top-2.5 text-xs text-gray-400'; }
        }
    } catch(e) { _refLat = null; _refLon = null; }
}

async function initReferralFilters() {
    if (referralFiltersReady) return;

    // Specialty multiselect (curated capabilities)
    let caps = [];
    try {
        const r = await fetch('/api/trust/capabilities');
        const d = await r.json();
        caps = (d.capabilities || []).map(c => ({ name: c, value: c, count: '' }));
    } catch(e) {
        caps = ['ICU','Maternity','Emergency','Oncology','Trauma','NICU',
                'Dialysis','Cardiology','Orthopedics','Neurology','Pediatrics',
                'Ophthalmology','Radiology','Pathology','Physiotherapy'
               ].map(c => ({ name: c, value: c, count: '' }));
    }
    createMultiSelect('ref-specialty-ms', caps, 'Select specialty...', async (selected) => {
        refSelectedSpecialties = selected;
        await refreshReferralStates();   // specialty → rescopes state list
    });

    // Procedure datalist (top 80 known procedures + free text allowed)
    try {
        const r  = await fetch('/api/referral/procedures');
        const d  = await r.json();
        const dl = document.getElementById('procedure-list');
        if (dl && d.procedures) {
            dl.innerHTML = d.procedures
                .map(p => '<option value="' + p.name.replace(/"/g, '&quot;') + '">' + p.count + ' facilities</option>')
                .join('');
        }
    } catch(e) { /* datalist optional */ }

    // Filter 2 + 3: initial unscoped state list (rescoped when specialty chosen)
    await refreshReferralStates();

    loadReferralShortlist();
    referralFiltersReady = true;
}

async function loadReferral() {
    const specialty = refSelectedSpecialties.join(',');  // all selected, OR logic in backend
    const procedure = document.getElementById('ref-procedure') ? document.getElementById('ref-procedure').value.trim() : '';
    const city      = document.getElementById('ref-city')      ? document.getElementById('ref-city').value      : '';
    if (!specialty && !procedure && !refSelectedStates.length) {
        document.getElementById('referral-results').innerHTML =
            '<p class="text-gray-400 py-8 text-center">Enter a specialty or procedure to search.</p>';
        return;
    }
    const params = new URLSearchParams({ limit: '20' });
    if (specialty)              params.set('specialty', specialty);
    if (procedure)              params.set('procedure', procedure);
    if (refSelectedStates.length) params.set('state', refSelectedStates.join(','));
    if (city)                   params.set('city', city);
    if (_refLat !== null)       params.set('lat', _refLat);
    if (_refLon !== null)       params.set('lon', _refLon);

    showLoading('referral-results');
    try {
        const res  = await fetch('/api/referral/search?' + params);
        const data = await res.json();
        const container = document.getElementById('referral-results');
        if (data.error)  { container.innerHTML = '<p class="text-red-500 py-4">' + data.error + '</p>'; return; }
        if (!data.facilities || !data.facilities.length) {
            const specLabel = specialty ? specialty.split(',').join(' or ') : 'selected specialty';
            const procNote  = procedure ? ' · procedure filter \"' + procedure + '\" may be too narrow' : '';
            container.innerHTML = '<div class="text-center py-8"><p class="text-gray-600 mb-1">No facilities match <strong>' + specLabel + '</strong>' + (procedure ? ' + <strong>' + procedure + '</strong>' : '') + (city ? ' in <strong>' + city + '</strong>' : '') + '.</p><p class="text-xs text-gray-400">The district count reflects the specialty filter only. Procedure filters are applied on top — try removing the procedure to see all ' + specLabel + ' facilities.' + procNote + '</p></div>';
            return;
        }
        container.innerHTML = data.facilities.map(function(f, i) {
            // Citations block
            var cites = (f.citations || []).map(function(c) {
                return '<div class="text-xs bg-gray-50 rounded p-2 mt-1 border-l-2 border-brand-red">' +
                    '<span class="font-medium text-gray-500">[' + c.field + ']</span> ' +
                    '<span class="text-gray-700">“' + c.text + '”</span></div>';
            }).join('');
            var citesHtml = cites
                ? '<details class="mt-2"><summary class="text-xs text-brand-red cursor-pointer font-medium">' +
                  'Evidence citations (' + f.citations.length + ')</summary><div class="mt-1">' + cites + '</div></details>'
                : '';

            // Missing / suspicious evidence
            var missingHtml = (f.missing_evidence || []).length
                ? '<div class="flex flex-wrap gap-1 mt-2">' +
                  (f.missing_evidence).map(function(m) {
                      return '<span class="text-xs px-2 py-0.5 rounded bg-orange-50 text-orange-700 border border-orange-200">⚠ ' + m + '</span>';
                  }).join('') + '</div>'
                : '';

            // Distance badge
            var distBadge = f.distance_km !== null && f.distance_km !== undefined
                ? '<span class="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">📍 ' + f.distance_km + ' km</span>'
                : '';

            // Trust badge
            var trustCls = f.trust_score >= 0.7 ? 'bg-green-100 text-green-700'
                         : f.trust_score >= 0.4 ? 'bg-yellow-100 text-yellow-700'
                         : 'bg-red-100 text-red-700';

            return '<div class="bg-white rounded-xl p-4 shadow-sm border hover:shadow-md transition">' +
                '<div class="flex justify-between items-start">' +
                    '<div class="flex-1">' +
                        '<div class="flex items-center gap-2 flex-wrap">' +
                            '<span class="text-xs bg-brand-dark text-white px-2 py-0.5 rounded">#' + (i+1) + '</span>' +
                            '<h4 class="font-semibold text-brand-dark">' + (f.name || f.unique_id) + '</h4>' +
                            distBadge +
                        '</div>' +
                        '<p class="text-sm text-gray-500 mt-0.5">' +
                            (f.city || '') + (f.city && f.state ? ', ' : '') + (f.state || '') +
                            (f.organization_type ? ' · <em>' + f.organization_type + '</em>' : '') +
                        '</p>' +
                        (f.match_reasons && f.match_reasons.length
                            ? '<div class="mt-1 text-xs text-green-700">' + f.match_reasons.join(' · ') + '</div>' : '') +
                        citesHtml +
                        missingHtml +
                    '</div>' +
                    '<div class="text-right ml-4 shrink-0">' +
                        '<div class="text-2xl font-bold text-brand-dark">' + (f.rank_score * 100).toFixed(0) + '</div>' +
                        '<div class="text-xs text-gray-400 mb-1">rank</div>' +
                        '<span class="text-xs px-2 py-0.5 rounded ' + trustCls + '">Trust ' + (f.trust_score * 100).toFixed(0) + '%</span>' +
                        '<br><button onclick="addToShortlist(\'' + f.unique_id + '\',\'' + (f.name || '').replace(/\'/g, '') + '\')" ' +
                            'class="mt-2 text-xs border border-brand-red text-brand-red rounded px-2 py-1 hover:bg-red-50">+ Shortlist</button>' +
                    '</div>' +
                '</div>' +
            '</div>';
        }).join('');
    } catch(e) { console.error('Referral load failed:', e); }
}

async function addToShortlist(facilityId, name) {
    try {
        const res  = await fetch('/api/referral/shortlist/' + encodeURIComponent(facilityId), { method: 'POST' });
        const data = await res.json();
        if (data.saved) {
            const panel = document.getElementById('referral-shortlist-panel');
            if (panel) panel.classList.remove('hidden');
            loadReferralShortlist();
        } else {
            alert('Could not save: ' + (data.error || 'unknown error'));
        }
    } catch(e) { alert('Shortlist save failed.'); }
}

async function loadReferralShortlist() {
    const panel = document.getElementById('referral-shortlist-panel');
    const items = document.getElementById('referral-shortlist-items');
    if (!items) return;
    try {
        const res  = await fetch('/api/referral/shortlist');
        const data = await res.json();
        const rows = data.shortlist || [];
        if (!rows.length) { if (panel) panel.classList.add('hidden'); return; }
        if (panel) panel.classList.remove('hidden');
        items.innerHTML = rows.map(function(r) {
            return '<div class="bg-white rounded-lg p-3 border flex justify-between items-center">' +
                '<div>' +
                    '<span class="font-medium text-sm text-brand-dark">' + (r.name || r.facility_id) + '</span>' +
                    '<span class="text-xs text-gray-400 ml-2">' + (r.address_city || '') + (r.state_normalized ? ', ' + r.state_normalized : '') + '</span>' +
                '</div>' +
                '<button onclick="removeFromShortlist(\'' + r.facility_id + '\')" class="text-xs text-gray-400 hover:text-red-500 ml-3">✕</button>' +
            '</div>';
        }).join('');
    } catch(e) { /* persist unavailable */ }
}

async function removeFromShortlist(facilityId) {
    try {
        await fetch('/api/referral/shortlist/' + encodeURIComponent(facilityId), { method: 'DELETE' });
        loadReferralShortlist();
    } catch(e) {}
}

function toggleShortlist() {
    const panel = document.getElementById('referral-shortlist-panel');
    if (panel) panel.classList.toggle('hidden');
}

// --- Data Readiness ---
let _reviewDecisions = {};  // facility_id -> decision (cached from last load)

function showReadinessTab(tab) {
    ['overview','review','states'].forEach(function(t) {
        document.getElementById('readiness-tab-' + t).classList.toggle('hidden', t !== tab);
        var btn = document.getElementById('tab-' + t);
        if (btn) {
            btn.className = t === tab
                ? 'readiness-tab px-4 py-2 text-sm font-medium border-b-2 border-brand-red text-brand-red'
                : 'readiness-tab px-4 py-2 text-sm font-medium border-b-2 border-transparent text-gray-500 hover:text-brand-dark';
        }
    });
    if (tab === 'review')  loadReviewQueue('all');
    if (tab === 'states')  loadStateBreakdown();
}

async function loadReadiness() {
    showLoading('readiness-overview');
    try {
        const res  = await fetch('/api/readiness/profile');
        const data = await res.json();
        const overview = document.getElementById('readiness-overview');
        if (data.error) { overview.innerHTML = '<p class="text-red-500 py-4">' + data.error + '</p>'; return; }
        const coverage = data.coverage || {};
        const entries  = Object.entries(coverage).sort(function(a,b) { return b[1].pct - a[1].pct; });
        overview.innerHTML =
            '<div class="stat-card"><div class="value">' + (data.total_records || 0).toLocaleString() + '</div><div class="label">Facilities Profiled</div></div>' +
            '<div class="stat-card"><div class="value">' + (data.fields_profiled || entries.length) + '</div><div class="label">Fields Analyzed</div></div>' +
            '<div class="stat-card"><div class="value">' + (data.enrichment_priorities || []).length + '</div><div class="label">Fields Below 50%</div></div>' +
            '<div class="stat-card cursor-pointer hover:shadow-md" onclick="showReadinessTab(&apos;review&apos;)">' +
                '<div class="value text-orange-500">!</div><div class="label">Review Queue</div></div>';
        const priorities = document.getElementById('readiness-priorities');
        priorities.innerHTML = entries.map(function(entry) {
            var field = entry[0], v = entry[1];
            var barColor  = v.pct > 80 ? '#22c55e' : v.pct > 50 ? '#eab308' : '#dc2626';
            var textClass = v.pct > 80 ? 'text-green-600' : v.pct > 50 ? 'text-yellow-600' : 'text-red-600';
            return '<div class="bg-white rounded-lg p-3 border flex items-center justify-between hover:shadow-sm transition">' +
                '<div class="min-w-[140px]"><span class="font-medium text-sm">' + field + '</span>' +
                '<span class="text-xs text-gray-400 ml-2">' + (v.count || 0).toLocaleString() + ' / ' + (v.total || 0).toLocaleString() + '</span></div>' +
                '<div class="flex items-center gap-3 flex-1 ml-4">' +
                    '<div class="progress-bar flex-1"><div class="fill" style="width:' + v.pct + '%;background:' + barColor + '"></div></div>' +
                    '<span class="text-sm font-semibold w-14 text-right ' + textClass + '">' + v.pct + '%</span>' +
                '</div></div>';
        }).join('');
        if ((data.enrichment_priorities || []).length) {
            priorities.innerHTML += '<h4 class="font-semibold text-brand-dark mt-6 mb-2">Priority Fields for Enrichment (&lt; 50% coverage)</h4>' +
                data.enrichment_priorities.map(function(e) {
                    return '<div class="bg-red-50 rounded-lg p-3 border border-red-100 flex items-center justify-between">' +
                        '<span class="font-medium text-sm text-red-800">' + e.field + '</span>' +
                        '<span class="text-sm text-red-600 font-semibold">' + e.pct + '% — ' + (e.missing || 0).toLocaleString() + ' missing</span></div>';
                }).join('');
        }
        // Pre-load review decisions cache
        fetch('/api/readiness/reviews').then(r => r.json()).then(d => {
            (d.reviews || []).forEach(function(r) { _reviewDecisions[r.facility_id] = r.decision; });
            var badge = document.getElementById('review-badge');
            if (badge) badge.textContent = (d.total || 0) + ' reviewed';
        }).catch(function(){});
    } catch(e) { console.error('Readiness load failed:', e); }
}

let _currentReviewFilter = 'all';
let _allFlagged = [];

async function loadReviewQueue(filter) {
    _currentReviewFilter = filter || 'all';
    // Update filter button styles
    ['all','pending','approved','rejected'].forEach(function(f) {
        var btn = document.getElementById('rfilt-' + f);
        if (btn) btn.className = f === _currentReviewFilter
            ? 'review-filter-btn text-xs px-3 py-1 rounded border border-brand-red bg-brand-red text-white'
            : 'review-filter-btn text-xs px-3 py-1 rounded border text-gray-600 hover:bg-gray-50';
    });

    var container = document.getElementById('readiness-flags');
    if (!container) return;
    if (!_allFlagged.length) {
        container.innerHTML = '<div class="flex items-center py-6 gap-3"><div class="animate-spin rounded-full h-6 w-6 border-b-2 border-brand-red"></div><span class="text-gray-500 text-sm">Loading flagged records...</span></div>';
        try {
            var res  = await fetch('/api/readiness/flags?limit=80');
            var data = await res.json();
            _allFlagged = data.flagged || [];
            var badge = document.getElementById('review-badge');
            if (badge) badge.textContent = _allFlagged.length + ' flagged';
        } catch(e) { container.innerHTML = '<p class="text-red-500">Failed to load flags.</p>'; return; }
    }

    var toShow = _allFlagged.filter(function(f) {
        var dec = _reviewDecisions[f.unique_id] || 'pending';
        if (_currentReviewFilter === 'all')      return true;
        if (_currentReviewFilter === 'pending')  return dec === 'pending';
        if (_currentReviewFilter === 'approved') return dec === 'approved';
        if (_currentReviewFilter === 'rejected') return dec === 'rejected';
        return true;
    });

    if (!toShow.length) {
        container.innerHTML = '<p class="text-gray-400 py-8 text-center">No records in this category.</p>';
        return;
    }

    container.innerHTML = toShow.map(function(f) {
        var dec    = _reviewDecisions[f.unique_id] || 'pending';
        var decCls = dec === 'approved' ? 'bg-green-50 border-green-200' : dec === 'rejected' ? 'bg-red-50 border-red-200' : 'bg-white';
        var flagHtml = (f.flag_reasons || []).map(function(r) {
            return '<span class="text-xs px-2 py-0.5 rounded bg-orange-50 text-orange-700 border border-orange-200 mr-1">⚠ ' + r + '</span>';
        }).join('');
        var safeId = (f.unique_id || '').replace(/'/g, '');
        var safeName = (f.name || '').replace(/'/g, '').replace(/"/g, '');
        var flagsJson = JSON.stringify(f.flag_reasons || []).replace(/'/g, "\'");
        return '<div class="rounded-xl p-4 border shadow-sm ' + decCls + ' transition" id="flag-row-' + safeId + '">' +
            '<div class="flex justify-between items-start">' +
                '<div class="flex-1">' +
                    '<div class="flex items-center gap-2 flex-wrap">' +
                        '<h4 class="font-semibold text-brand-dark text-sm">' + (f.name || f.unique_id) + '</h4>' +
                        '<span class="text-xs text-gray-400">' + (f.city || '') + (f.state ? ', ' + f.state : '') + '</span>' +
                        (f.organization_type ? '<span class="text-xs text-gray-400 italic">' + f.organization_type + '</span>' : '') +
                    '</div>' +
                    '<div class="flex flex-wrap gap-1 mt-1">' + flagHtml + '</div>' +
                    (f.description_snippet ? '<p class="text-xs text-gray-500 mt-1 italic">“' + f.description_snippet + '…”</p>' : '') +
                    '<div class="mt-2 flex items-center gap-2">' +
                        '<input type="text" placeholder="Add note..." id="note-' + safeId + '" class="border rounded px-2 py-1 text-xs flex-1" value="">' +
                    '</div>' +
                '</div>' +
                '<div class="flex flex-col gap-1 ml-4 shrink-0">' +
                    '<button onclick="saveReviewDecision(\'' + safeId + '\',\'approved\',\'' + flagsJson + '\')" ' +
                        'class="text-xs px-3 py-1 rounded bg-green-100 text-green-700 hover:bg-green-200 font-medium">✓ Approve</button>' +
                    '<button onclick="saveReviewDecision(\'' + safeId + '\',\'rejected\',\'' + flagsJson + '\')" ' +
                        'class="text-xs px-3 py-1 rounded bg-red-100 text-red-700 hover:bg-red-200 font-medium">✕ Reject</button>' +
                    '<button onclick="saveReviewDecision(\'' + safeId + '\',\'needs_review\',\'' + flagsJson + '\')" ' +
                        'class="text-xs px-3 py-1 rounded bg-yellow-100 text-yellow-700 hover:bg-yellow-200 font-medium">✎ Flag</button>' +
                    (dec !== 'pending' ? '<span class="text-xs text-center text-gray-400 mt-1">' + dec + '</span>' : '') +
                '</div>' +
            '</div>' +
        '</div>';
    }).join('');
}

async function saveReviewDecision(facilityId, decision, flagReasonsJson) {
    var noteEl = document.getElementById('note-' + facilityId);
    var note   = noteEl ? noteEl.value.trim() : '';
    var flagReason = '';
    try { flagReason = JSON.parse(flagReasonsJson.replace(/\'/g, "'")).join('; '); } catch(e) {}
    try {
        var params = new URLSearchParams({ facility_id: facilityId, decision: decision, flag_reason: flagReason, note: note });
        var res  = await fetch('/api/readiness/review?' + params, { method: 'POST' });
        var data = await res.json();
        if (data.saved) {
            _reviewDecisions[facilityId] = decision;
            // Update row styling without full reload
            var row = document.getElementById('flag-row-' + facilityId);
            if (row) {
                row.className = row.className.replace(/bg-\S+ border-\S+/g, '').trim();
                row.classList.add(decision === 'approved' ? 'bg-green-50' : decision === 'rejected' ? 'bg-red-50' : 'bg-yellow-50');
                row.classList.add(decision === 'approved' ? 'border-green-200' : decision === 'rejected' ? 'border-red-200' : 'border-yellow-200');
            }
            // Refresh badge
            var reviewed = Object.keys(_reviewDecisions).filter(function(k) { return _reviewDecisions[k] !== 'pending'; }).length;
            var badge = document.getElementById('review-badge');
            if (badge) badge.textContent = _allFlagged.length + ' flagged · ' + reviewed + ' reviewed';
        }
    } catch(e) { alert('Save failed.'); }
}

async function loadStateBreakdown() {
    var container = document.getElementById('readiness-states');
    if (!container) return;
    container.innerHTML = '<div class="text-gray-400 text-sm py-4">Loading...</div>';
    try {
        var res  = await fetch('/api/readiness/state-summary');
        var data = await res.json();
        var rows = data.states || [];
        if (!rows.length) { container.innerHTML = '<p class="text-gray-400">No data.</p>'; return; }
        var cols = [
            { key: 'state',       label: 'State' },
            { key: 'total',       label: 'Facilities' },
            { key: 'desc_pct',    label: 'Description %' },
            { key: 'spec_pct',    label: 'Specialties %' },
            { key: 'coord_pct',   label: 'Coordinates %' },
            { key: 'doctors_pct', label: 'Doctors %' },
            { key: 'equip_pct',   label: 'Equipment %' },
        ];
        var thead = '<tr>' + cols.map(function(c) {
            return '<th class="px-3 py-2 text-left text-xs font-semibold text-gray-500 bg-gray-50 border-b whitespace-nowrap">' + c.label + '</th>';
        }).join('') + '</tr>';
        var tbody = rows.map(function(r) {
            return '<tr class="hover:bg-gray-50">' + cols.map(function(c) {
                var val = r[c.key];
                if (c.key === 'total') return '<td class="px-3 py-2 text-sm font-medium">' + (val || 0).toLocaleString() + '</td>';
                if (c.key === 'state') return '<td class="px-3 py-2 text-sm font-medium text-brand-dark">' + (val || '—') + '</td>';
                var pct = parseFloat(val) || 0;
                var cls = pct > 80 ? 'text-green-600' : pct > 50 ? 'text-yellow-600' : 'text-red-600';
                return '<td class="px-3 py-2 text-sm font-semibold ' + cls + '">' + pct + '%</td>';
            }).join('') + '</tr>';
        }).join('');
        container.innerHTML = '<table class="w-full border-collapse text-sm"><thead>' + thead + '</thead><tbody>' + tbody + '</tbody></table>';
    } catch(e) { container.innerHTML = '<p class="text-red-400">Failed to load.</p>'; }
}

// --- Init ---
document.addEventListener('DOMContentLoaded', function() { showPage('dashboard'); });
