"""Identity resolution module — phone-based worker matching with fuzzy name validation.

Handles BUG-07 (duplicate names) by using phone as primary key.
"""

from rapidfuzz import fuzz
from app.pipeline.normalise import normalise_phone


def resolve_identity(raw_phone: str, raw_name: str, workers_df) -> dict:
    """Resolve a raw phone+name to a canonical worker_id.

    Phone is the primary key for matching (not name, due to BUG-07 duplicates).
    Name similarity is used only as a confidence signal.

    Returns dict with: worker_id, confidence, name_similarity, status
    """
    norm_phone, phone_status = normalise_phone(raw_phone)

    if phone_status != 'OK':
        return {
            'worker_id': None,
            'confidence': 0.0,
            'name_similarity': 0.0,
            'status': 'UNRESOLVABLE_PHONE'
        }

    match = workers_df[workers_df['phone'] == norm_phone]

    if match.empty:
        return {
            'worker_id': None,
            'confidence': 0.0,
            'name_similarity': 0.0,
            'status': 'PHONE_NOT_IN_REGISTRY'
        }

    worker = match.iloc[0]

    # Name similarity as secondary validation
    name_score = fuzz.token_sort_ratio(
        str(raw_name).lower().strip(),
        str(worker['name']).lower().strip()
    ) / 100.0

    if name_score >= 0.85:
        confidence = 0.95
    elif name_score >= 0.50:
        confidence = 0.70
    elif name_score >= 0.30:
        confidence = 0.50  # possible phone reassignment
    else:
        confidence = 0.35

    return {
        'worker_id': worker['worker_id'],
        'confidence': round(confidence, 3),
        'name_similarity': round(name_score, 3),
        'status': 'RESOLVED' if confidence >= 0.7 else 'LOW_CONFIDENCE'
    }
