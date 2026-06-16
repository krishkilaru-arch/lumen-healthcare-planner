"""Track 4: Data Readiness Desk — dataset quality profiling and review."""

import re
from fastapi import APIRouter, Query
from db import query, execute, SYNCED_SCHEMA, APP_SCHEMA

router = APIRouter(prefix="/api/readiness", tags=["readiness"])

PROFILE_FIELDS = [
    'name', 'description', 'address_city', 'state_normalized',
    'latitude', 'longitude', 'specialties', 'capability', 'procedure',
    'equipment', 'phone_numbers', 'email', 'websites', 'numberDoctors',
    'capacity', 'yearEstablished', 'source_urls', 'organization_type',
    'officialPhone', 'officialWebsite', 'facebookLink',
]
NUMERIC_FIELDS = {'latitude', 'longitude'}

# India bounding box
INDIA_LAT = (6.0, 37.5)
INDIA_LON = (68.0, 97.5)

HIGH_ACUITY_KW = ['icu', 'intensive care', 'trauma center', 'nicu',
                   'emergency surgery', 'cardiac surgery', 'neurosurgery']


def _flag_reasons(row: dict) -> list:
    """Detect suspicious claims / contradictions in a facility record."""
    flags = []
    desc  = (row.get('description') or '').strip()
    cap   = (row.get('capability')  or '').lower()
    equip = (row.get('equipment')   or '')
    name  = (row.get('name')        or '').lower()

    # 1. Claims high-acuity care but description is very short
    if any(kw in cap for kw in HIGH_ACUITY_KW) and len(desc) < 80:
        flags.append('claims high-acuity care but description < 80 chars')

    # 2. Year established out of range
    year_raw = str(row.get('yearEstablished') or '').strip()
    if year_raw and year_raw not in ('', 'null', 'None'):
        try:
            yr = int(re.sub(r'[^0-9]', '', year_raw)[:4])
            if yr > 2025:
                flags.append(f'year established in the future ({yr})')
            elif yr < 1900:
                flags.append(f'year established implausibly old ({yr})')
        except (ValueError, TypeError):
            flags.append(f'year established not parseable: "{year_raw[:20]}"')

    # 3. Coordinates outside India
    try:
        lat = float(row.get('latitude') or 0)
        lon = float(row.get('longitude') or 0)
        if lat and lon:
            if not (INDIA_LAT[0] <= lat <= INDIA_LAT[1]):
                flags.append(f'latitude {lat:.3f} outside India ({INDIA_LAT[0]}–{INDIA_LAT[1]}°N)')
            if not (INDIA_LON[0] <= lon <= INDIA_LON[1]):
                flags.append(f'longitude {lon:.3f} outside India ({INDIA_LON[0]}–{INDIA_LON[1]}°E)')
    except (TypeError, ValueError):
        pass

    # 4. Clinic/dispensary name but claims ICU/Trauma/NICU
    basic_names = ['clinic', 'dispensary', 'pharmacy', 'medical store']
    if any(w in name for w in basic_names) and any(kw in cap for kw in ['icu', 'trauma', 'nicu']):
        flags.append('name suggests basic facility but claims ICU / Trauma / NICU')

    # 5. High capability word count but no equipment data — likely copy-pasted
    cap_words = [c.strip() for c in re.split(r'[,;\n|]', cap) if c.strip()]
    if len(cap_words) > 12 and (not equip or equip in ('', '[]')):
        flags.append(f'lists {len(cap_words)} capability items but no equipment data (possible copy-paste)')

    # 6. Doctor count present but description is empty/very short
    num_docs = str(row.get('numberDoctors') or '').strip()
    if num_docs and num_docs not in ('', 'null', 'None') and len(desc) < 30:
        flags.append('doctor count listed but description is missing or very short')

    return flags


# ---------------------------------------------------------------------------
# Existing endpoints
# ---------------------------------------------------------------------------

@router.get("/profile")
async def data_profile():
    """Full dataset profiling — coverage % for each field."""
    total = query(f'SELECT COUNT(*) as cnt FROM {SYNCED_SCHEMA}.facilities_full')[0]['cnt']
    coverage = {}
    for field in PROFILE_FIELDS:
        if field in NUMERIC_FIELDS:
            sql = f'SELECT COUNT(*) as cnt FROM {SYNCED_SCHEMA}.facilities_full WHERE "{field}" IS NOT NULL'
        else:
            sql = f"SELECT COUNT(*) as cnt FROM {SYNCED_SCHEMA}.facilities_full WHERE \"{field}\" IS NOT NULL AND \"{field}\" != '' AND \"{field}\" != '[]'"
        count = query(sql)[0]['cnt']
        coverage[field] = {
            'count': count, 'total': total,
            'pct': round(count / total * 100, 1) if total else 0,
        }
    priorities = sorted(
        [{'field': f, 'pct': v['pct'], 'missing': v['total'] - v['count']}
         for f, v in coverage.items() if v['pct'] < 50],
        key=lambda x: x['pct']
    )
    return {'total_records': total, 'fields_profiled': len(PROFILE_FIELDS),
            'coverage': coverage, 'enrichment_priorities': priorities}


@router.get("/state-summary")
async def state_summary():
    """Data completeness broken down by state (percentages)."""
    rows = query(f"""
        SELECT state_normalized AS state,
               COUNT(*) AS total,
               ROUND(AVG(CASE WHEN description IS NOT NULL AND description != '' THEN 100.0 ELSE 0.0 END), 1)                                                    AS desc_pct,
               ROUND(AVG(CASE WHEN specialties IS NOT NULL AND specialties != '' AND specialties != '[]' THEN 100.0 ELSE 0.0 END), 1)                           AS spec_pct,
               ROUND(AVG(CASE WHEN latitude IS NOT NULL THEN 100.0 ELSE 0.0 END), 1)                                                                            AS coord_pct,
               ROUND(AVG(CASE WHEN "numberDoctors" IS NOT NULL AND "numberDoctors" != '' THEN 100.0 ELSE 0.0 END), 1)                                          AS doctors_pct,
               ROUND(AVG(CASE WHEN equipment IS NOT NULL AND equipment != '' AND equipment != '[]' THEN 100.0 ELSE 0.0 END), 1)                                AS equip_pct
        FROM {SYNCED_SCHEMA}.facilities_full
        GROUP BY state_normalized
        ORDER BY COUNT(*) DESC
        LIMIT 35
    """)
    return {'states': rows}


@router.get("/gaps")
async def data_gaps(field: str = Query("numberDoctors")):
    """Sample facilities missing a specific field."""
    rows = query(f"""
        SELECT unique_id, name, address_city, state_normalized AS state
        FROM {SYNCED_SCHEMA}.facilities_full
        WHERE ("{field}" IS NULL OR "{field}" = '' OR "{field}" = '[]')
        LIMIT 50
    """)
    return {'field': field, 'missing_count': len(rows), 'sample': rows}


@router.get("/completeness-by-type")
async def completeness_by_type():
    rows = query(f"""
        SELECT organization_type,
               COUNT(*) AS total,
               ROUND(AVG(CASE WHEN description IS NOT NULL AND description != '' THEN 1.0 ELSE 0.0 END) * 100, 1) AS desc_pct,
               ROUND(AVG(CASE WHEN specialties IS NOT NULL AND specialties != '' AND specialties != '[]' THEN 1.0 ELSE 0.0 END) * 100, 1) AS spec_pct,
               ROUND(AVG(CASE WHEN "numberDoctors" IS NOT NULL AND "numberDoctors" != '' THEN 1.0 ELSE 0.0 END) * 100, 1) AS doctors_pct
        FROM {SYNCED_SCHEMA}.facilities_full
        WHERE organization_type IS NOT NULL
        GROUP BY organization_type
        ORDER BY COUNT(*) DESC
    """)
    return {'by_type': rows}


# ---------------------------------------------------------------------------
# New: Flag engine + review queue
# ---------------------------------------------------------------------------

@router.get("/flags")
async def get_flags(limit: int = Query(80)):
    """Return facilities with suspicious claims or data quality issues."""
    rows = query(f"""
        SELECT unique_id, name, organization_type, address_city, state_normalized,
               description, capability, equipment, "numberDoctors",
               "yearEstablished", latitude, longitude
        FROM {SYNCED_SCHEMA}.facilities_full
        WHERE (
            (LENGTH(COALESCE(description, '')) < 80
             AND capability IS NOT NULL AND capability NOT IN ('', '[]'))
            OR ("yearEstablished" IS NOT NULL AND "yearEstablished" NOT IN ('', 'null')
                AND "yearEstablished" ~ '^[0-9]'
                AND (CAST(LEFT("yearEstablished", 4) AS INTEGER) > 2025
                     OR CAST(LEFT("yearEstablished", 4) AS INTEGER) < 1900))
            OR (latitude  IS NOT NULL AND (latitude  < 6   OR latitude  > 37.5))
            OR (longitude IS NOT NULL AND (longitude < 68  OR longitude > 97.5))
            OR (LENGTH(COALESCE(capability, '')) > 300
                AND (equipment IS NULL OR equipment IN ('', '[]')))
        )
        LIMIT %s
    """, (limit * 3,))

    flagged = []
    for row in rows:
        reasons = _flag_reasons(row)
        if reasons:
            flagged.append({
                'unique_id':          row['unique_id'],
                'name':               row['name'],
                'organization_type':  row['organization_type'],
                'city':               row['address_city'],
                'state':              row['state_normalized'],
                'description_snippet': (row.get('description') or '')[:150].strip(),
                'year_established':   row.get('yearEstablished'),
                'lat':                row.get('latitude'),
                'lon':                row.get('longitude'),
                'flag_reasons':       reasons,
                'flag_count':         len(reasons),
            })

    flagged.sort(key=lambda x: x['flag_count'], reverse=True)
    return {'flagged': flagged[:limit], 'total': len(flagged)}


@router.post("/review")
async def save_review(
    facility_id: str = Query(...),
    decision:    str = Query(...),   # approved | rejected | needs_review
    flag_reason: str = Query(''),
    note:        str = Query(''),
):
    """Persist reviewer decision to Lakebase app_data.review_decisions."""
    try:
        execute(
            f"INSERT INTO {APP_SCHEMA}.review_decisions "
            f"(facility_id, decision, flag_reason, note) VALUES (%s, %s, %s, %s) "
            f"ON CONFLICT (user_id, facility_id) DO UPDATE "
            f"SET decision = EXCLUDED.decision, flag_reason = EXCLUDED.flag_reason, "
            f"note = EXCLUDED.note, updated_at = NOW()",
            (facility_id, decision, flag_reason, note)
        )
        return {'saved': True, 'facility_id': facility_id, 'decision': decision}
    except Exception as e:
        return {'saved': False, 'error': str(e)}


@router.get("/reviews")
async def get_reviews():
    """Return all saved reviewer decisions."""
    try:
        rows = query(
            f"SELECT * FROM {APP_SCHEMA}.review_decisions ORDER BY updated_at DESC"
        )
        return {'reviews': rows, 'total': len(rows)}
    except Exception as e:
        return {'reviews': [], 'error': str(e)}
