"""Track 3: Referral Copilot — ranked facility recommendations with citations."""

import math
from fastapi import APIRouter, Query
from db import query, execute, SYNCED_SCHEMA, APP_SCHEMA
from scoring import compute_trust_score, safe_json_parse

router = APIRouter(prefix="/api/referral", tags=["referral"])


def haversine(lat1, lon1, lat2, lon2):
    """Distance in km between two points."""
    R = 6371
    try:
        lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        return R * 2 * math.asin(math.sqrt(a))
    except (TypeError, ValueError):
        return None


def _extract_citations(row: dict, keywords: list) -> list:
    """Extract text snippets from evidence fields where any keyword was found."""
    citations = []
    fields = [
        ('description', row.get('description', '') or ''),
        ('capability',  row.get('capability', '')  or ''),
        ('procedure',   row.get('procedure', '')   or ''),
        ('equipment',   row.get('equipment', '')   or ''),
        ('specialties', row.get('specialties', '') or ''),
    ]
    for field_name, text in fields:
        tl = text.lower()
        for kw in keywords:
            if kw.lower() in tl:
                idx   = tl.find(kw.lower())
                start = max(0, idx - 40)
                end   = min(len(text), idx + len(kw) + 60)
                snippet = text[start:end].strip()
                if start > 0:        snippet = '…' + snippet
                if end < len(text):  snippet = snippet + '…'
                citations.append({'field': field_name, 'keyword': kw, 'text': snippet})
                break  # one citation per field
    return citations


def _missing_evidence(row: dict, specialty: str = None) -> list:
    """List evidence fields that are absent or suspiciously sparse."""
    missing = []
    if not row.get('capacity') or str(row.get('capacity', '')).strip() in ('', 'null', 'None'):
        missing.append('capacity unknown')
    if not row.get('numberDoctors') or str(row.get('numberDoctors', '')).strip() in ('', 'null', 'None'):
        missing.append('staff count not listed')
    if not row.get('equipment') or row.get('equipment') in ('', '[]'):
        missing.append('no equipment data')
    if not row.get('source_urls') or row.get('source_urls') in ('', '[]'):
        missing.append('no source URL to verify')
    # Suspicious: claims specialty but description is very short
    desc = row.get('description', '') or ''
    if specialty and specialty.lower() in (row.get('specialties', '') or '').lower() and len(desc) < 50:
        missing.append('very short description for claimed specialty')
    return missing


@router.get("/search")
async def referral_search(
    specialty:  str   = Query(None),
    procedure:  str   = Query(None),
    state:      str   = Query(None),
    city:       str   = Query(None),
    lat:        float = Query(None, description="Patient latitude"),
    lon:        float = Query(None, description="Patient longitude"),
    limit:      int   = Query(20),
):
    """Find and rank facilities for a referral with citations and missing-evidence flags."""
    where_parts, params = [], []

    if specialty:
        # Support comma-separated specialties — OR logic across all
        spec_list = [s.strip() for s in specialty.split(',') if s.strip()]
        spec_conditions = []
        for sp in spec_list:
            kw = f'%{sp}%'
            spec_conditions.append(
                "(specialties ILIKE %s OR description ILIKE %s "
                "OR capability ILIKE %s OR procedure ILIKE %s)"
            )
            params.extend([kw, kw, kw, kw])
        where_parts.append('(' + ' OR '.join(spec_conditions) + ')')

    if procedure:
        where_parts.append('procedure ILIKE %s')
        params.append(f'%{procedure}%')

    if state:
        state_list   = [s.strip().upper() for s in state.split(',') if s.strip()]
        placeholders = ','.join(['%s'] * len(state_list))
        where_parts.append(f'UPPER(state_normalized) IN ({placeholders})')
        params.extend(state_list)

    if city:
        where_parts.append('address_city ILIKE %s')
        params.append(f'%{city}%')

    where_sql = ('WHERE ' + ' AND '.join(where_parts)) if where_parts else ''
    sql = f'SELECT * FROM {SYNCED_SCHEMA}.facilities_full {where_sql} LIMIT %s'
    params.append(limit * 4)  # over-fetch for re-ranking

    rows  = query(sql, tuple(params))
    kws   = [w for w in [specialty, procedure] if w]  # keywords for citations

    results = []
    for row in rows:
        trust       = compute_trust_score(row)
        trust_score = trust['overall_score']

        # Proximity
        proximity_score = 0.5
        distance_km     = None
        if lat and lon and row.get('latitude') and row.get('longitude'):
            distance_km = haversine(lat, lon, row['latitude'], row['longitude'])
            if distance_km is not None:
                proximity_score = max(0, 1 - distance_km / 500)

        # Capacity
        try:
            capacity_score = min(int(row.get('capacity') or 0) / 500, 1.0)
        except (ValueError, TypeError):
            capacity_score = 0.3

        # Relevance
        specs     = safe_json_parse(row.get('specialties'))
        procs     = safe_json_parse(row.get('procedure'))
        relevance = 0.5
        if specialty and any(specialty.lower() in s.lower() for s in specs):
            relevance = 1.0
        elif specialty and specialty.lower() in (row.get('description', '') or '').lower():
            relevance = 0.8
        if procedure and any(procedure.lower() in p.lower() for p in procs):
            relevance = max(relevance, 0.9)

        rank_score = (relevance * 0.35 + trust_score * 0.30 +
                      proximity_score * 0.20 + capacity_score * 0.15)

        # Citations — what text justifies this recommendation
        citations = _extract_citations(row, kws) if kws else []

        # Missing / suspicious evidence
        missing = _missing_evidence(row, specialty)

        # Human-readable match reasons
        reasons = []
        if relevance >= 0.9:
            reasons.append(f"Specialty match: {specialty or procedure}")
        elif relevance >= 0.8:
            reasons.append(f"Mentioned in description")
        if trust_score >= 0.7:
            reasons.append("High trust score")
        if distance_km and distance_km < 50:
            reasons.append(f"{distance_km:.0f} km away")
        elif distance_km:
            reasons.append(f"{distance_km:.0f} km away")

        results.append({
            'unique_id':       row.get('unique_id'),
            'name':            row.get('name'),
            'city':            row.get('address_city'),
            'state':           row.get('state_normalized') or row.get('address_stateOrRegion'),
            'organization_type': row.get('organization_type'),
            'specialties':     specs[:5],
            'trust_score':     trust_score,
            'rank_score':      round(rank_score, 3),
            'distance_km':     round(distance_km, 1) if distance_km else None,
            'match_reasons':   reasons,
            'citations':       citations,
            'missing_evidence': missing,
            'source_urls':     row.get('source_urls'),
        })

    results.sort(key=lambda x: x['rank_score'], reverse=True)
    return {
        'facilities': results[:limit],
        'query': {'specialty': specialty, 'procedure': procedure, 'state': state, 'city': city},
    }


@router.post("/shortlist/{facility_id}")
async def add_to_referral_shortlist(facility_id: str, label: str = Query('')):
    """Save a facility to the referral shortlist."""
    try:
        execute(
            f"INSERT INTO {APP_SCHEMA}.shortlists (facility_id, track, label) "
            f"VALUES (%s, 'referral', %s) ON CONFLICT (user_id, facility_id, track) "
            f"DO UPDATE SET label = EXCLUDED.label",
            (facility_id, label)
        )
        return {'saved': True}
    except Exception as e:
        return {'saved': False, 'error': str(e)}


@router.delete("/shortlist/{facility_id}")
async def remove_from_referral_shortlist(facility_id: str):
    """Remove a facility from the referral shortlist."""
    try:
        execute(
            f"DELETE FROM {APP_SCHEMA}.shortlists WHERE facility_id = %s AND track = 'referral'",
            (facility_id,)
        )
        return {'removed': True}
    except Exception as e:
        return {'removed': False, 'error': str(e)}


@router.get("/shortlist")
async def get_referral_shortlist():
    """Return saved referral shortlist with facility details."""
    try:
        rows = query(
            f"SELECT s.id, s.facility_id, s.label, s.created_at, "
            f"f.name, f.address_city, f.state_normalized, f.specialties, f.source_urls "
            f"FROM {APP_SCHEMA}.shortlists s "
            f"JOIN {SYNCED_SCHEMA}.facilities_full f ON s.facility_id = f.unique_id "
            f"WHERE s.track = 'referral' ORDER BY s.created_at DESC"
        )
        return {'shortlist': rows}
    except Exception as e:
        return {'shortlist': [], 'error': str(e)}


@router.get("/procedures")
async def list_procedures():
    """Top procedures by facility count, short enough to show as menu items."""
    try:
        rows = query(
            f"SELECT procedure FROM {SYNCED_SCHEMA}.facilities_full "
            f"WHERE procedure IS NOT NULL AND procedure NOT IN ('', '[]') LIMIT 8000"
        )
        counts: dict = {}
        for r in rows:
            for p in safe_json_parse(r['procedure']):
                p = p.strip()
                # keep only human-readable short labels (skip long descriptions / numbers)
                if 3 < len(p) <= 60 and p[0].isalpha():
                    counts[p] = counts.get(p, 0) + 1
        top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:80]
        return {'procedures': [{'name': p, 'count': c} for p, c in top]}
    except Exception as e:
        return {'error': str(e)}


@router.get("/specialties")
async def list_specialties():
    """List all specialties with facility counts."""
    try:
        rows = query(f"SELECT specialties FROM {SYNCED_SCHEMA}.facilities_full WHERE specialties IS NOT NULL AND specialties != '' AND specialties != '[]' LIMIT 5000")
        spec_counts = {}
        for r in rows:
            for s in safe_json_parse(r['specialties']):
                spec_counts[s] = spec_counts.get(s, 0) + 1
        sorted_specs = sorted(spec_counts.items(), key=lambda x: x[1], reverse=True)
        return {'specialties': [{'name': s, 'count': c} for s, c in sorted_specs]}
    except Exception as e:
        return {'error': str(e)}


@router.get("/facility/{facility_id}")
async def facility_detail(facility_id: str):
    """Get full facility details."""
    rows = query(f'SELECT * FROM {SYNCED_SCHEMA}.facilities_full WHERE unique_id = %s', (facility_id,))
    if not rows:
        return {'error': 'Not found'}
    row = rows[0]
    trust = compute_trust_score(row)
    return {
        **row,
        'specialties_parsed': safe_json_parse(row.get('specialties')),
        'capabilities_parsed': safe_json_parse(row.get('capability')),
        'procedures_parsed': safe_json_parse(row.get('procedure')),
        'trust': trust,
    }
