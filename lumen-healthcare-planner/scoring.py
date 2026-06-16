"""Trust scoring engine — computes facility trustworthiness from data quality signals."""

import json
import logging

logger = logging.getLogger(__name__)


def safe_json_parse(val):
    """Safely parse a JSON string field, returning a flat list of strings."""
    if not val or val in ('', '[]', 'null', 'None'):
        return []
    try:
        parsed = json.loads(val)
        if not isinstance(parsed, list):
            parsed = [parsed]
        # Flatten: extract only string items, skip dicts/lists
        result = []
        for item in parsed:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                # Try to extract a name/value from dict
                result.append(item.get('name', item.get('id', str(item))))
            else:
                result.append(str(item))
        return result
    except (json.JSONDecodeError, TypeError):
        return []


def compute_trust_score(facility: dict) -> dict:
    """Compute trust score for a facility record.
    
    Returns dict with overall_score, completeness, verification, recency,
    evidence list, and field_coverage map.
    """
    # --- Completeness (40% weight) ---
    critical_fields = ['name', 'address_city', 'state_normalized',
                       'latitude', 'longitude', 'organization_type',
                       'specialties', 'unique_id']
    important_fields = ['description', 'phone_numbers', 'capability',
                        'procedure', 'equipment', 'capacity', 'numberDoctors']
    nice_fields = ['email', 'websites', 'yearEstablished',
                   'officialPhone', 'source_urls', 'facebookLink']

    def field_present(f):
        v = facility.get(f)
        return v is not None and str(v).strip() not in ('', 'null', '[]', 'None')

    critical_score = sum(1 for f in critical_fields if field_present(f)) / len(critical_fields)
    important_score = sum(1 for f in important_fields if field_present(f)) / len(important_fields)
    nice_score = sum(1 for f in nice_fields if field_present(f)) / len(nice_fields)
    completeness = critical_score * 0.5 + important_score * 0.35 + nice_score * 0.15

    # --- Verification (35% weight) ---
    verification_signals = 0.0
    verification_max = 4.0

    # Source URLs present
    if field_present('source_urls'):
        verification_signals += 1.0

    # Description length (longer = more verified content)
    desc = facility.get('description', '') or ''
    if len(desc) > 200:
        verification_signals += 1.0
    elif len(desc) > 50:
        verification_signals += 0.5

    # Rich structured data (capability/procedure/equipment)
    cap_count = len(safe_json_parse(facility.get('capability')))
    proc_count = len(safe_json_parse(facility.get('procedure')))
    equip_count = len(safe_json_parse(facility.get('equipment')))
    richness = min((cap_count + proc_count + equip_count) / 10.0, 1.0)
    verification_signals += richness

    # Multiple contact methods
    contacts = sum(1 for f in ['phone_numbers', 'email', 'websites', 'officialPhone'] if field_present(f))
    verification_signals += min(contacts / 3.0, 1.0)

    verification = verification_signals / verification_max

    # --- Recency (25% weight) ---
    year_str = facility.get('yearEstablished', '') or ''
    try:
        year = int(year_str)
        if year >= 2015:
            recency = 1.0
        elif year >= 2000:
            recency = 0.8
        elif year >= 1990:
            recency = 0.6
        else:
            recency = 0.4
    except (ValueError, TypeError):
        recency = 0.3  # Unknown = low recency

    # --- Overall ---
    overall = completeness * 0.40 + verification * 0.35 + recency * 0.25

    # --- Evidence ---
    evidence = []
    if field_present('source_urls'):
        evidence.append({'type': 'source_url', 'value': facility.get('source_urls', '')[:100]})
    if cap_count > 0:
        evidence.append({'type': 'capabilities', 'value': f'{cap_count} capabilities listed'})
    if proc_count > 0:
        evidence.append({'type': 'procedures', 'value': f'{proc_count} procedures listed'})
    if field_present('yearEstablished'):
        evidence.append({'type': 'established', 'value': year_str})
    if contacts >= 2:
        evidence.append({'type': 'contacts', 'value': f'{contacts} contact methods'})

    # --- Field coverage ---
    all_fields = critical_fields + important_fields + nice_fields
    field_coverage = {f: field_present(f) for f in all_fields}

    return {
        'overall_score': round(overall, 3),
        'completeness': round(completeness, 3),
        'verification': round(verification, 3),
        'recency': round(recency, 3),
        'evidence': evidence,
        'field_coverage': field_coverage,
    }
