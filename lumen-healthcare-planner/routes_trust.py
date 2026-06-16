"""Track 1: Facility Trust Desk — capability-based trust evaluation with citations.

Per hackathon requirements:
- Planner selects a CAPABILITY (ICU, maternity, emergency, oncology, trauma, NICU)
  and a REGION (state/city)
- Sees ranked facilities with trust signals (strong/partial/weak/no evidence)
- Expands a facility to inspect citations from source text
- Can override the assessment with a note

Cascading filter: Capability -> State (with count) -> City (with count) -> Results
"""

import json
from fastapi import APIRouter, Query
from db import query, execute, SYNCED_SCHEMA, APP_SCHEMA
from scoring import compute_trust_score, safe_json_parse

router = APIRouter(prefix="/api/trust", tags=["trust"])

# Capabilities that can be evaluated (per hackathon prompt)
CAPABILITIES = [
    'ICU', 'Maternity', 'Emergency', 'Oncology', 'Trauma', 'NICU',
    'Dialysis', 'Cardiology', 'Orthopedics', 'Neurology', 'Pediatrics',
    'Ophthalmology', 'Radiology', 'Pathology', 'Physiotherapy',
]

# Keywords for each capability (used to search in description/capability/procedure)
CAPABILITY_KEYWORDS = {
    'ICU': ['icu', 'intensive care', 'critical care', 'ventilator'],
    'Maternity': ['maternity', 'obstetrics', 'gynecology', 'obgyn', 'ob-gyn', 'delivery', 'antenatal', 'labour room', 'labor room', 'postnatal'],
    'Emergency': ['emergency', 'trauma', 'casualty', 'accident', '24/7', '24x7', '24 hour', 'ambulance'],
    'Oncology': ['oncology', 'cancer', 'chemotherapy', 'radiation therapy', 'tumor', 'tumour'],
    'Trauma': ['trauma', 'accident', 'fracture', 'orthopedic emergency', 'polytrauma'],
    'NICU': ['nicu', 'neonatal', 'newborn intensive', 'premature', 'neonatal icu'],
    'Dialysis': ['dialysis', 'hemodialysis', 'nephrology', 'renal'],
    'Cardiology': ['cardiology', 'cardiac', 'heart', 'angioplasty', 'bypass', 'cath lab', 'ecg', 'echo'],
    'Orthopedics': ['orthopedic', 'orthopaedic', 'joint replacement', 'fracture', 'spine', 'bone'],
    'Neurology': ['neurology', 'neuro', 'brain', 'stroke', 'epilepsy', 'neurosurgery'],
    'Pediatrics': ['pediatric', 'paediatric', 'children', 'child care', 'neonatal'],
    'Ophthalmology': ['ophthalmology', 'eye', 'cataract', 'lasik', 'retina', 'glaucoma'],
    'Radiology': ['radiology', 'x-ray', 'ct scan', 'mri', 'ultrasound', 'imaging'],
    'Pathology': ['pathology', 'laboratory', 'lab', 'blood test', 'diagnostic'],
    'Physiotherapy': ['physiotherapy', 'physical therapy', 'rehabilitation', 'rehab'],
}


def evaluate_capability_claim(row, capability):
    """Evaluate if a facility can actually do what it claims for a given capability.
    
    Returns trust_signal (strong/partial/weak/no_claim) and citations list.
    Handles comma-separated capabilities — evaluates the FIRST one for signal.
    """
    # Handle comma-separated: use first capability for signal evaluation
    cap = capability.split(',')[0].strip() if ',' in capability else capability
    keywords = CAPABILITY_KEYWORDS.get(cap, [cap.lower()])
    citations = []
    
    # Search across evidence fields
    fields_to_check = [
        ('description', row.get('description', '') or ''),
        ('capability', row.get('capability', '') or ''),
        ('procedure', row.get('procedure', '') or ''),
        ('equipment', row.get('equipment', '') or ''),
        ('specialties', row.get('specialties', '') or ''),
    ]
    
    for field_name, field_val in fields_to_check:
        if not field_val:
            continue
        text = field_val.lower()
        for kw in keywords:
            if kw in text:
                # Extract a citation snippet (surrounding context)
                idx = text.find(kw)
                start = max(0, idx - 40)
                end = min(len(field_val), idx + len(kw) + 60)
                snippet = field_val[start:end].strip()
                if start > 0:
                    snippet = '...' + snippet
                if end < len(field_val):
                    snippet = snippet + '...'
                citations.append({
                    'field': field_name,
                    'keyword': kw,
                    'text': snippet,
                })
                break  # one citation per field is enough
    
    # Determine trust signal based on number of corroborating fields
    num_fields = len(citations)
    has_source_url = bool(row.get('source_urls'))
    has_equipment = any(c['field'] == 'equipment' for c in citations)
    
    if num_fields >= 3 or (num_fields >= 2 and has_source_url):
        signal = 'strong'
    elif num_fields == 2 or (num_fields == 1 and (has_source_url or has_equipment)):
        signal = 'partial'
    elif num_fields == 1:
        signal = 'weak'
    else:
        signal = 'no_claim'
    
    return signal, citations


@router.get("/capabilities")
async def list_capabilities():
    """List available capabilities for filtering."""
    return {'capabilities': CAPABILITIES}


@router.get("/scores")
async def trust_scores(
    capability: str = Query(None),
    state: str = Query(None),
    city: str = Query(None),
    min_score: float = Query(0.0),
    limit: int = Query(30),
):
    """Get trust scores for facilities, optionally filtered by capability claim."""
    where_clauses = []
    params = []
    
    # Capability filter: support comma-separated capabilities (OR logic)
    if capability:
        caps = [c.strip() for c in capability.split(',') if c.strip()]
        keywords = []
        for cap in caps:
            for kw in CAPABILITY_KEYWORDS.get(cap, [cap.lower()])[:3]:
                if kw not in keywords:
                    keywords.append(kw)
        kw_conditions = []
        for kw in keywords[:9]:  # up to 3 per capability, max 9 total
            kw_conditions.append(
                "(LOWER(COALESCE(description,'')) || ' ' || LOWER(COALESCE(capability,'')) || ' ' || "
                "LOWER(COALESCE(procedure,'')) || ' ' || LOWER(COALESCE(specialties,''))) ILIKE %s"
            )
            params.append(f'%{kw}%')
        if kw_conditions:
            where_clauses.append('(' + ' OR '.join(kw_conditions) + ')')
    
    if state:
        state_list = [s.strip() for s in state.split(',') if s.strip()]
        if len(state_list) == 1:
            where_clauses.append('UPPER(state_normalized) = %s')
            params.append(state_list[0].upper())
        else:
            placeholders = ','.join(['%s'] * len(state_list))
            where_clauses.append(f'UPPER(state_normalized) IN ({placeholders})')
            params.extend([s.upper() for s in state_list])
    if city:
        where_clauses.append('address_city ILIKE %s')
        params.append(f'%{city}%')

    where_sql = (' WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''
    sql = f'SELECT * FROM {SYNCED_SCHEMA}.facilities_full{where_sql} LIMIT %s'
    params.append(limit * 3)

    rows = query(sql, tuple(params))
    results = []
    for row in rows:
        score_data = compute_trust_score(row)
        if score_data['overall_score'] < min_score:
            continue
        
        # Evaluate capability claim if specified
        cap_signal = None
        cap_citations = []
        if capability:
            cap_signal, cap_citations = evaluate_capability_claim(row, capability)
        
        results.append({
            'facility_id': row.get('unique_id'),
            'name': row.get('name'),
            'city': row.get('address_city'),
            'state': row.get('state_normalized') or row.get('address_stateOrRegion'),
            'capability_signal': cap_signal,
            'capability_citations': cap_citations,
            **score_data,
        })
    
    # Merge any saved user overrides — use first capability for override lookup
    primary_cap = capability.split(',')[0].strip() if capability and ',' in capability else capability
    if primary_cap and results:
        fids = [r['facility_id'] for r in results]
        ph   = ','.join(['%s'] * len(fids))
        try:
            saved = query(
                f"SELECT facility_id, user_signal, note FROM {APP_SCHEMA}.trust_overrides "
                f"WHERE capability = %s AND facility_id IN ({ph})",
                tuple([primary_cap] + fids)
            )
            override_map = {o['facility_id']: o for o in saved}
        except Exception:
            override_map = {}

        for r in results:
            ov = override_map.get(r['facility_id'])
            if ov:
                r['computed_signal'] = r['capability_signal']   # preserve original
                r['capability_signal'] = ov['user_signal']      # apply override
                r['user_override'] = {'signal': ov['user_signal'], 'note': ov['note']}
            else:
                r['user_override'] = None

    # Sort: strong > partial > weak > no_claim, then by trust score
    signal_order = {'strong': 0, 'partial': 1, 'weak': 2, 'no_claim': 3, None: 4}
    results.sort(key=lambda x: (signal_order.get(x.get('capability_signal'), 4), -x['overall_score']))
    return {'facilities': results[:limit], 'total': len(results), 'capability': capability}
