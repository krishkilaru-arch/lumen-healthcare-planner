"""Track 2: Medical Desert Planner — identify underserved regions."""

import math
import json as _json
import difflib
from fastapi import APIRouter, Query
from db import query, execute, SYNCED_SCHEMA, APP_SCHEMA

# ---------------------------------------------------------------------------
# Module-level NFHS cache + fuzzy district lookup
# ---------------------------------------------------------------------------
_nfhs_cache: dict | None = None

def _get_nfhs_map() -> dict:
    """Fetch NFHS data once and cache for the process lifetime."""
    global _nfhs_cache
    if _nfhs_cache is not None:
        return _nfhs_cache
    rows = query(f"""
        SELECT LOWER(district_name)                   AS district_key,
               district_name,
               state_ut,
               institutional_birth_5y_pct,
               births_attended_by_skilled_hp_5y_10_pct,
               hh_member_covered_health_insurance_pct
        FROM {SYNCED_SCHEMA}.nfhs_5_district_health_indicators
    """)
    _nfhs_cache = {r['district_key']: r for r in rows}
    return _nfhs_cache

def _fuzzy_nfhs(district_name: str) -> dict | None:
    """Look up NFHS row for a district using exact then fuzzy match (cutoff 0.85)."""
    if not district_name:
        return None
    nfhs_map = _get_nfhs_map()
    key = district_name.lower().strip()
    # Exact first
    if key in nfhs_map:
        return nfhs_map[key]
    # Skip obvious non-district values (numbers, dates, garbage)
    if not key or not key[0].isalpha():
        return None
    # Fuzzy — 0.85 cutoff proven to have zero false positives in dataset
    matches = difflib.get_close_matches(key, list(nfhs_map.keys()), n=1, cutoff=0.85)
    return nfhs_map[matches[0]] if matches else None


def _safe_float(v):
    """Return None for NULL, NaN, or Inf — all are JSON-unsafe as floats."""
    if v is None:
        return None
    try:
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, 6)
    except (TypeError, ValueError):
        return None

router = APIRouter(prefix="/api/deserts", tags=["deserts"])


def _capability_where_deserts(capability: str) -> tuple:
    """Return (sql_fragment, params) for a capability keyword search.
    Mirrors the same logic used in routes_trust and app.py so all counts stay consistent.
    """
    try:
        from routes_trust import CAPABILITY_KEYWORDS
        keywords = CAPABILITY_KEYWORDS.get(capability, [capability.lower()])
    except Exception:
        keywords = [capability.lower()]
    kw_conditions, params = [], []
    for kw in keywords[:3]:
        kw_conditions.append(
            "(LOWER(COALESCE(description,'')) || ' ' || LOWER(COALESCE(capability,'')) || ' '"
            " || LOWER(COALESCE(procedure,'')) || ' ' || LOWER(COALESCE(specialties,''))) ILIKE %s"
        )
        params.append(f'%{kw}%')
    fragment = '(' + ' OR '.join(kw_conditions) + ')' if kw_conditions else 'TRUE'
    return fragment, params


@router.get("/analysis")
async def desert_analysis(
    state:      str = Query(None),
    capability: str = Query(None),
    threshold:  int = Query(5, description="Max facilities to be considered a desert"),
):
    """Find medical deserts — districts with few facilities for the selected capability."""
    where_parts, params = [], []
    if state:
        where_parts.append('state_normalized ILIKE %s')
        params.append(f'%{state}%')
    if capability:
        cap_sql, cap_params = _capability_where_deserts(capability)
        where_parts.append(cap_sql)
        params.extend(cap_params)

    where_clause = ('WHERE ' + ' AND '.join(where_parts)) if where_parts else ''

    sql = f"""
        SELECT state_normalized as state, address_city as district,
               COUNT(*) as facility_count,
               AVG(latitude) as avg_lat, AVG(longitude) as avg_lon
        FROM {SYNCED_SCHEMA}.facilities_full
        {where_clause}
        GROUP BY state_normalized, address_city
        HAVING COUNT(*) <= %s
        ORDER BY COUNT(*) ASC
    """
    params.append(threshold)
    rows = query(sql, tuple(params))

    # NFHS data for uncertainty signal — use cached fuzzy lookup

    deserts = []
    for r in rows:
        count = r['facility_count']
        if count == 0:
            severity = 'critical'
        elif count <= 1:
            severity = 'high'
        elif count <= 3:
            severity = 'moderate'
        else:
            severity = 'low'

        # Uncertainty: fuzzy-match district to NFHS data
        nfhs = _fuzzy_nfhs(r['district'] or '')
        if count == 0:
            # No facilities at all — could be a true desert OR a data gap
            confidence = 'data_limited'
            confidence_note = 'No facilities found. May reflect missing data rather than confirmed absence.'
        elif nfhs:
            # NFHS data available — cross-check outcomes
            births_pct  = _safe_float(nfhs.get('institutional_birth_5y_pct')) or 0
            skilled_pct = _safe_float(nfhs.get('births_attended_by_skilled_hp_5y_10_pct')) or 0
            poor_outcomes = births_pct < 60 or skilled_pct < 60
            if poor_outcomes:
                confidence = 'confirmed_gap'
                confidence_note = f'NFHS-5 confirms poor outcomes: {births_pct:.0f}% institutional births, {skilled_pct:.0f}% skilled birth attendance.'
            else:
                confidence = 'possible_gap'
                confidence_note = f'Low facility count but NFHS-5 outcomes are acceptable ({births_pct:.0f}% institutional births, {skilled_pct:.0f}% skilled attendance).'
        else:
            confidence = 'possible_gap'
            confidence_note = 'No NFHS-5 data available for this district to confirm gap severity.'

        deserts.append({
            'state':           r['state'],
            'district':        r['district'] or 'Unknown',
            'facility_count':  count,
            'severity':        severity,
            'confidence':      confidence,
            'confidence_note': confidence_note,
            'avg_lat':         _safe_float(r['avg_lat']),
            'avg_lon':         _safe_float(r['avg_lon']),
        })

    summary = {
        'critical':       sum(1 for d in deserts if d['severity'] == 'critical'),
        'high':           sum(1 for d in deserts if d['severity'] == 'high'),
        'moderate':       sum(1 for d in deserts if d['severity'] == 'moderate'),
        'low':            sum(1 for d in deserts if d['severity'] == 'low'),
        'confirmed_gaps': sum(1 for d in deserts if d['confidence'] == 'confirmed_gap'),
        'data_limited':   sum(1 for d in deserts if d['confidence'] == 'data_limited'),
    }
    return {'deserts': deserts, 'summary': summary, 'threshold': threshold, 'capability': capability}


@router.get("/facilities")
async def desert_facilities(
    state:      str = Query(...),
    district:   str = Query(...),
    capability: str = Query(None),
):
    """Drill into the actual facilities behind a desert district."""
    where_parts = [
        'state_normalized ILIKE %s',
        'address_city = %s',
    ]
    params = [f'%{state}%', district]
    if capability:
        cap_sql, cap_params = _capability_where_deserts(capability)
        where_parts.append(cap_sql)
        params.extend(cap_params)
    where_sql = 'WHERE ' + ' AND '.join(where_parts)
    rows = query(f"""
        SELECT unique_id, name, organization_type, address_city,
               state_normalized, description,
               capability, specialties, source_urls,
               latitude, longitude
        FROM {SYNCED_SCHEMA}.facilities_full
        {where_sql}
        ORDER BY name
        LIMIT 50
    """, tuple(params))
    return {
        'facilities': [
            {**r, 'latitude': _safe_float(r.get('latitude')), 'longitude': _safe_float(r.get('longitude'))}
            for r in rows
        ],
        'district':   district,
        'state':      state,
        'capability': capability,
    }


@router.get("/scenarios")
async def list_scenarios():
    """Return saved planning scenarios for Track 2."""
    try:
        rows = query(
            f"SELECT id, name, filters_json, results_json, notes, created_at "
            f"FROM {APP_SCHEMA}.scenarios WHERE track = 'deserts' ORDER BY created_at DESC LIMIT 20"
        )
        return {'scenarios': rows}
    except Exception as e:
        return {'scenarios': [], 'error': str(e)}


@router.post("/scenarios")
async def save_scenario(
    name:     str = Query(...),
    filters:  str = Query(..., description="JSON-encoded filter state"),
    notes:    str = Query(''),
):
    """Save a planning scenario (filter state + summary)."""
    try:
        execute(
            f"INSERT INTO {APP_SCHEMA}.scenarios (user_id, name, track, filters_json, notes) "
            f"VALUES (%s, %s, 'deserts', %s::jsonb, %s)",
            ('default', name, filters, notes)
        )
        return {'saved': True, 'name': name}
    except Exception as e:
        return {'saved': False, 'error': str(e)}


@router.get("/nfhs-overlay")
async def nfhs_overlay(state: str = Query(None)):
    """Overlay NFHS-5 health indicators with facility counts per district."""
    where_clause = ""
    params = []
    if state:
        where_clause = 'WHERE n.state_ut ILIKE %s'
        params.append(f"%{state}%")

    sql = f"""
        SELECT n.district_name, n.state_ut,
               n.hh_member_covered_health_insurance_pct         AS insurance_pct,
               n.institutional_birth_5y_pct                    AS institutional_births_pct,
               n.births_attended_by_skilled_hp_5y_10_pct       AS skilled_births_pct,
               COALESCE(f.cnt, 0) as facility_count
        FROM {SYNCED_SCHEMA}.nfhs_5_district_health_indicators n
        LEFT JOIN (
            SELECT address_city, COUNT(*) as cnt
            FROM {SYNCED_SCHEMA}.facilities_full
            GROUP BY address_city
        ) f ON LOWER(f.address_city) = LOWER(n.district_name)
        {where_clause}
        ORDER BY facility_count ASC
        LIMIT 100
    """
    rows = query(sql, tuple(params))
    return {'districts': rows}


@router.get("/specialty-gaps")
async def specialty_gaps(specialty: str = Query("cardiology")):
    """Find districts missing a specific specialty."""
    sql = f"""
        SELECT state_normalized as state, address_city as district,
               COUNT(*) as total_facilities,
               SUM(CASE WHEN specialties ILIKE %s THEN 1 ELSE 0 END) as with_specialty
        FROM {SYNCED_SCHEMA}.facilities_full
        WHERE address_city IS NOT NULL
        GROUP BY state_normalized, address_city
        HAVING SUM(CASE WHEN specialties ILIKE %s THEN 1 ELSE 0 END) = 0
        ORDER BY COUNT(*) DESC
        LIMIT 50
    """
    rows = query(sql, (f"%{specialty}%", f"%{specialty}%"))
    return {'specialty': specialty, 'gaps': rows}
