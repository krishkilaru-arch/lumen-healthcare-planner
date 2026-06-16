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
    const cap = trustSelectedCaps.join(',');
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
    const cap    = trustSelectedCaps.join(',');
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

// --- Desert Map (Leaflet) ---
function initDesertMap(deserts) {
    const mapEl = document.getElementById('desert-map');
    if (!mapEl) return;
    if (desertMap) { desertMap.remove(); desertMap = null; }
    desertMap = L.map('desert-map').setView([22.5, 80], 4.5);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 12,
        attribution: '&copy; OpenStreetMap'
    }).addTo(desertMap);
    const sevColors = { critical: '#dc2626', high: '#ea580c', moderate: '#ca8a04', low: '#16a34a' };
    deserts.forEach(function(d) {
        if (!d.avg_lat || !d.avg_lon) return;
        var color = sevColors[d.severity] || '#6b7280';
        var radius = d.severity === 'critical' ? 12 : d.severity === 'high' ? 10 : 8;
        L.circleMarker([d.avg_lat, d.avg_lon], {
            radius: radius,
            fillColor: color,
            color: '#fff',
            weight: 1,
            fillOpacity: 0.75
        }).addTo(desertMap)
          .bindPopup('<strong>' + (d.district || 'Unknown') + '</strong><br>' +
                     d.state + '<br>' +
                     '<span style="color:' + color + ';font-weight:bold">' + d.severity + '</span> — ' +
                     d.facility_count + ' facilities<br>' +
                     '<em>' + (d.confidence_note || '') + '</em>');
    });
    setTimeout(function() { desertMap.invalidateSize(); }, 200);
}

async function loadDesertScenarios() {
    const el = document.getElementById('desert-scenarios');
    if (!el) return;
    try {
        const res = await fetch('/api/deserts/scenarios');
        const data = await res.json();
        const scenarios = data.scenarios || [];
        if (!scenarios.length) { el.innerHTML = ''; return; }
        el.innerHTML = '<h4 class="text-sm font-semibold text-brand-dark mb-2">Saved Scenarios</h4>' +
            scenarios.map(function(s) {
                return '<div class="text-xs bg-white border rounded p-2 mb-1"><span class="font-medium">' + s.name + '</span> <span class="text-gray-400 ml-2">' + (s.created_at || '').slice(0, 10) + '</span></div>';
            }).join('');
    } catch(e) { /* silent */ }
}

// --- Referral Copilot ---
let refSelectedSpecs = [];
let refSelectedStates = [];
let refInitDone = false;
let refLat = null, refLon = null;

async function refreshReferralStates() {
    const spec = refSelectedSpecs.join(',');
    const proc = document.getElementById('ref-procedure') ? document.getElementById('ref-procedure').value : '';
    const params = new URLSearchParams();
    if (spec) params.set('capability', spec);
    if (proc) params.set('procedure', proc);
    const url = '/api/filters/states' + (params.toString() ? '?' + params : '');
    let states = [];
    try {
        const res = await fetch(url);
        const data = await res.json();
        states = data.states || [];
    } catch(e) { states = []; }
    refSelectedStates = [];
    createMultiSelect('ref-state-ms', states, 'Select state(s)...', async (selected) => {
        refSelectedStates = selected;
        await loadCitiesForStates(selected, 'ref-city', spec, proc);
    });
}

async function initReferralFilters() {
    if (refInitDone) return;
    const states = await loadStates();
    // Build specialty multi-select from capabilities + common specialties
    let specs = [];
    try {
        const res = await fetch('/api/trust/capabilities');
        const data = await res.json();
        specs = (data.capabilities || []).map(c => ({ name: c, value: c, count: '' }));
    } catch(e) {
        specs = ['Cardiology','Neurology','Orthopedics','Oncology','Pediatrics','Ophthalmology',
                 'Emergency','ICU','Maternity','Dialysis','Radiology'].map(c => ({ name: c, value: c, count: '' }));
    }
    createMultiSelect('ref-specialty-ms', specs, 'Select specialty...', async (selected) => {
        refSelectedSpecs = selected;
        await refreshReferralStates();
    });
    createMultiSelect('ref-state-ms', states, 'Select state(s)...', async (selected) => {
        refSelectedStates = selected;
        const spec = refSelectedSpecs.join(',');
        const proc = document.getElementById('ref-procedure') ? document.getElementById('ref-procedure').value : '';
        await loadCitiesForStates(selected, 'ref-city', spec, proc);
    });
    refInitDone = true;
}

function resolveNearCity() {
    // Simple geocode approximation — use facility coords for known cities
    const input = document.getElementById('ref-near');
    const status = document.getElementById('ref-near-status');
    if (!input || !input.value.trim()) { refLat = null; refLon = null; if (status) status.textContent = ''; return; }
    // For demo, set approximate coords for major Indian cities
    const cities = {
        'mumbai': [19.076, 72.877], 'delhi': [28.613, 77.209], 'bangalore': [12.972, 77.594],
        'bengaluru': [12.972, 77.594], 'hyderabad': [17.385, 78.486], 'chennai': [13.083, 80.270],
        'kolkata': [22.572, 88.364], 'pune': [18.520, 73.856], 'ahmedabad': [23.022, 72.571],
        'jaipur': [26.912, 75.787], 'lucknow': [26.846, 80.946], 'patna': [25.594, 85.137],
        'bhopal': [23.259, 77.412], 'thiruvananthapuram': [8.524, 76.936], 'chandigarh': [30.733, 76.779],
    };
    const key = input.value.trim().toLowerCase();
    if (cities[key]) {
        refLat = cities[key][0]; refLon = cities[key][1];
        if (status) status.textContent = '✓';
    } else {
        refLat = null; refLon = null;
        if (status) status.textContent = '?';
    }
}

async function loadReferral() {
    const specialty = refSelectedSpecs.join(',');
    const procedure = document.getElementById('ref-procedure') ? document.getElementById('ref-procedure').value : '';
    const states = refSelectedStates;
    const city = document.getElementById('ref-city') ? document.getElementById('ref-city').value : '';
    const params = new URLSearchParams();
    if (specialty) params.set('specialty', specialty);
    if (procedure) params.set('procedure', procedure);
    if (states.length) params.set('state', states.join(','));
    if (city) params.set('city', city);
    if (refLat && refLon) { params.set('lat', refLat); params.set('lon', refLon); }
    params.set('limit', '20');

    showLoading('referral-results');
    try {
        const res = await fetch('/api/referral/search?' + params);
        const data = await res.json();
        const container = document.getElementById('referral-results');
        if (data.error) { container.innerHTML = '<p class="text-red-500 py-4">' + data.error + '</p>'; return; }
        const facs = data.facilities || [];
        if (!facs.length) {
            container.innerHTML = '<p class="text-gray-500 py-8 text-center">No matching facilities found. Try broader filters.</p>';
            return;
        }
        container.innerHTML = facs.map(function(f) {
            var distTxt = f.distance_km ? '<span class="text-xs text-blue-600 font-medium">' + f.distance_km + ' km</span>' : '';
            var reasons = (f.match_reasons || []).map(function(r) { return '<span class="text-xs bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded">' + r + '</span>'; }).join(' ');
            var citations = (f.citations || []).map(function(c) {
                return '<div class="text-xs bg-gray-50 rounded p-2 mt-1 border-l-2 border-brand-red"><span class="font-medium text-gray-600">[' + c.field + ']</span> "' + c.text + '"</div>';
            }).join('');
            var missing = (f.missing_evidence || []).map(function(m) {
                return '<span class="text-xs bg-orange-50 text-orange-600 px-1.5 py-0.5 rounded">' + m + '</span>';
            }).join(' ');
            return '<div class="bg-white rounded-xl p-4 shadow-sm border hover:shadow-md transition">' +
                '<div class="flex justify-between items-start">' +
                    '<div class="flex-1">' +
                        '<div class="flex items-center gap-2">' +
                            '<h4 class="font-semibold text-brand-dark">' + (f.name || f.unique_id) + '</h4>' +
                            distTxt +
                        '</div>' +
                        '<p class="text-sm text-gray-500 mt-0.5">' + (f.city || '') + (f.city && f.state ? ', ' : '') + (f.state || '') +
                            (f.organization_type ? ' <span class="text-xs text-gray-400">(' + f.organization_type + ')</span>' : '') + '</p>' +
                        (reasons ? '<div class="mt-1.5 flex flex-wrap gap-1">' + reasons + '</div>' : '') +
                        (citations ? '<details class="mt-2"><summary class="text-xs text-brand-red cursor-pointer font-medium">Citations (' + f.citations.length + ')</summary><div class="mt-1">' + citations + '</div></details>' : '') +
                        (missing ? '<div class="mt-2 flex flex-wrap gap-1">' + missing + '</div>' : '') +
                    '</div>' +
                    '<div class="text-right ml-4">' +
                        '<div class="text-2xl font-bold ' + (f.rank_score >= 0.7 ? 'text-green-600' : f.rank_score >= 0.4 ? 'text-yellow-600' : 'text-red-600') + '">' +
                            (f.rank_score * 100).toFixed(0) + '</div>' +
                        '<div class="text-xs text-gray-400">rank score</div>' +
                        '<button onclick="addToShortlist(\'' + f.unique_id + '\',\'' + (f.name || '').replace(/'/g, '') + '\')" class="mt-2 text-xs text-brand-red border border-brand-red rounded px-2 py-1 hover:bg-red-50">+ Shortlist</button>' +
                    '</div>' +
                '</div>' +
            '</div>';
        }).join('');
    } catch(e) { console.error('Referral load failed:', e); }
}

async function addToShortlist(facilityId, name) {
    try {
        const res = await fetch('/api/referral/shortlist/' + facilityId + '?label=' + encodeURIComponent(name), { method: 'POST' });
        const data = await res.json();
        if (data.saved) alert('Added to shortlist: ' + name);
        else alert('Failed: ' + (data.error || ''));
    } catch(e) { alert('Failed to save.'); }
}

function toggleShortlist() {
    const panel = document.getElementById('referral-shortlist-panel');
    if (panel) panel.classList.toggle('hidden');
}

// --- Data Readiness ---
let readinessLoaded = false;

function showReadinessTab(tab) {
    ['overview', 'review', 'states'].forEach(function(t) {
        const el = document.getElementById('readiness-tab-' + t);
        const btn = document.getElementById('tab-' + t);
        if (el) el.classList.toggle('hidden', t !== tab);
        if (btn) {
            btn.classList.toggle('border-brand-red', t === tab);
            btn.classList.toggle('text-brand-red', t === tab);
            btn.classList.toggle('border-transparent', t !== tab);
            btn.classList.toggle('text-gray-500', t !== tab);
        }
    });
}

async function loadReadiness() {
    if (readinessLoaded) return;
    showLoading('readiness-overview');
    try {
        const res = await fetch('/api/readiness/profile');
        const data = await res.json();
        const cov = data.coverage || {};
        const total = data.total_records || 0;
        const priorities = data.enrichment_priorities || [];

        document.getElementById('readiness-overview').innerHTML =
            '<div class="stat-card"><div class="value">' + total.toLocaleString() + '</div><div class="label">Total Records</div></div>' +
            '<div class="stat-card"><div class="value">' + data.fields_profiled + '</div><div class="label">Fields Profiled</div></div>' +
            '<div class="stat-card"><div class="value">' + priorities.length + '</div><div class="label">Fields < 50%</div></div>' +
            '<div class="stat-card"><div class="value">' + (priorities.length > 0 ? priorities[0].pct.toFixed(0) + '%' : '—') + '</div><div class="label">Worst Field</div></div>';

        // Field coverage bars
        const fields = Object.keys(cov).sort(function(a, b) { return cov[b].pct - cov[a].pct; });
        document.getElementById('readiness-priorities').innerHTML = fields.map(function(f) {
            var pct = cov[f].pct;
            var color = pct >= 80 ? 'bg-green-500' : pct >= 50 ? 'bg-yellow-500' : 'bg-red-500';
            return '<div class="flex items-center gap-3">' +
                '<span class="text-xs font-mono w-40 text-gray-600">' + f + '</span>' +
                '<div class="flex-1 bg-gray-100 rounded-full h-3 overflow-hidden"><div class="h-full rounded-full ' + color + '" style="width:' + pct + '%"></div></div>' +
                '<span class="text-xs text-gray-500 w-12 text-right">' + pct.toFixed(0) + '%</span>' +
            '</div>';
        }).join('');
    } catch(e) { console.error('Readiness profile failed:', e); }

    // Load state summary
    try {
        const res = await fetch('/api/readiness/state-summary');
        const data = await res.json();
        const states = data.states || [];
        document.getElementById('readiness-states').innerHTML =
            '<table class="w-full text-xs"><thead class="bg-gray-50"><tr>' +
            '<th class="px-2 py-1.5 text-left">State</th><th class="px-2 py-1.5">Facilities</th>' +
            '<th class="px-2 py-1.5">Description</th><th class="px-2 py-1.5">Specialties</th>' +
            '<th class="px-2 py-1.5">Coordinates</th><th class="px-2 py-1.5">Doctors</th>' +
            '<th class="px-2 py-1.5">Equipment</th></tr></thead><tbody>' +
            states.map(function(s) {
                function pctCell(v) { var c = v >= 80 ? 'text-green-600' : v >= 50 ? 'text-yellow-600' : 'text-red-600'; return '<td class="px-2 py-1 text-center ' + c + '">' + (v || 0).toFixed(0) + '%</td>'; }
                return '<tr class="border-t"><td class="px-2 py-1 font-medium">' + (s.state || '—') + '</td>' +
                    '<td class="px-2 py-1 text-center">' + s.total + '</td>' +
                    pctCell(s.desc_pct) + pctCell(s.spec_pct) + pctCell(s.coord_pct) +
                    pctCell(s.doctors_pct) + pctCell(s.equip_pct) + '</tr>';
            }).join('') +
            '</tbody></table>';
    } catch(e) { console.error('Readiness states failed:', e); }

    // Load review queue
    loadReviewQueue('all');
    readinessLoaded = true;
}

let _reviewData = [];

async function loadReviewQueue(filter) {
    // Highlight active filter button
    document.querySelectorAll('.review-filter-btn').forEach(function(btn) {
        btn.classList.remove('bg-brand-red', 'text-white', 'border-brand-red');
        btn.classList.add('text-gray-600');
    });
    var activeBtn = document.getElementById('rfilt-' + filter);
    if (activeBtn) { activeBtn.classList.add('bg-brand-red', 'text-white', 'border-brand-red'); activeBtn.classList.remove('text-gray-600'); }

    showLoading('readiness-flags');
    try {
        const res = await fetch('/api/readiness/flags?limit=80');
        const data = await res.json();
        _reviewData = data.flags || [];
        // Also fetch existing decisions to merge
        let decisions = {};
        try {
            const dRes = await fetch('/api/readiness/decisions');
            const dData = await dRes.json();
            (dData.decisions || []).forEach(function(d) { decisions[d.facility_id] = d; });
        } catch(e) { /* no decisions yet */ }

        let flags = _reviewData.map(function(f) {
            f._decision = decisions[f.unique_id] || null;
            return f;
        });

        // Apply filter
        if (filter === 'pending')  flags = flags.filter(function(f) { return !f._decision; });
        if (filter === 'approved') flags = flags.filter(function(f) { return f._decision && f._decision.decision === 'approved'; });
        if (filter === 'rejected') flags = flags.filter(function(f) { return f._decision && f._decision.decision === 'rejected'; });

        var badge = document.getElementById('review-badge');
        if (badge) badge.textContent = flags.length + ' records';

        document.getElementById('readiness-flags').innerHTML = flags.length === 0
            ? '<p class="text-gray-400 text-sm py-4 text-center">No records in this category.</p>'
            : flags.map(function(f) {
                var reasons = (f.flag_reasons || []).map(function(r) {
                    return '<span class="text-xs bg-orange-50 text-orange-700 px-1.5 py-0.5 rounded">' + r + '</span>';
                }).join(' ');
                var dec = f._decision;
                var decBadge = dec
                    ? '<span class="text-xs px-2 py-0.5 rounded font-medium ' +
                      (dec.decision === 'approved' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700') + '">' +
                      dec.decision + '</span>'
                    : '';
                return '<div class="bg-white rounded-lg border p-3">' +
                    '<div class="flex justify-between items-start">' +
                        '<div class="flex-1">' +
                            '<span class="font-medium text-sm text-brand-dark">' + (f.name || f.unique_id) + '</span>' +
                            '<span class="text-xs text-gray-400 ml-2">' + (f.state_normalized || '') + '</span> ' + decBadge +
                            '<div class="mt-1 flex flex-wrap gap-1">' + reasons + '</div>' +
                        '</div>' +
                        '<div class="flex gap-1">' +
                            '<button onclick="submitReview(\'' + f.unique_id + '\',\'approved\')" class="text-xs px-2 py-1 rounded border border-green-500 text-green-600 hover:bg-green-50">Approve</button>' +
                            '<button onclick="submitReview(\'' + f.unique_id + '\',\'rejected\')" class="text-xs px-2 py-1 rounded border border-red-500 text-red-600 hover:bg-red-50">Reject</button>' +
                        '</div>' +
                    '</div>' +
                '</div>';
            }).join('');
    } catch(e) { console.error('Review queue failed:', e); }
}

async function submitReview(facilityId, decision) {
    try {
        const params = new URLSearchParams({ decision: decision, note: '' });
        const res = await fetch('/api/readiness/review/' + facilityId + '?' + params, { method: 'POST' });
        const data = await res.json();
        if (data.saved) loadReviewQueue('all');
        else alert('Save failed: ' + (data.error || ''));
    } catch(e) { alert('Review save failed.'); }
}

// --- Page Init ---
document.addEventListener('DOMContentLoaded', function() {
    showPage('dashboard');
});
