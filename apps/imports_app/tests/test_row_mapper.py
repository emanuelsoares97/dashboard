from apps.imports_app.parsers.row_mapper import build_raw_hash


def test_build_raw_hash_stability_with_different_key_order():
    payload_a = {
        'agent_name': 'Ana',
        'start_date': '2026-01-01 10:00:00',
        'end_date': '2026-01-01 10:10:00',
        'final_outcome': 'Retido',
    }
    payload_b = {
        'final_outcome': 'Retido',
        'end_date': '2026-01-01 10:10:00',
        'agent_name': 'Ana',
        'start_date': '2026-01-01 10:00:00',
    }

    assert build_raw_hash(payload_a) == build_raw_hash(payload_b)


def test_build_raw_hash_changes_when_payload_changes():
    payload_a = {
        'agent_name': 'Ana',
        'start_date': '2026-01-01 10:00:00',
        'end_date': '2026-01-01 10:10:00',
        'final_outcome': 'Retido',
    }
    payload_b = {
        'agent_name': 'Ana',
        'start_date': '2026-01-01 10:00:00',
        'end_date': '2026-01-01 10:10:00',
        'final_outcome': 'Nao Retido',
    }

    assert build_raw_hash(payload_a) != build_raw_hash(payload_b)
