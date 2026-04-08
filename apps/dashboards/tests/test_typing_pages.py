from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone as dj_timezone

from apps.dashboards.services.typing import build_typing_analysis_payload


@pytest.fixture
def client(dashboard_client_factory):
    test_client, _ = dashboard_client_factory(username='supervisor-typing', group_names=['Supervisores'])
    return test_client


@pytest.mark.django_db
def test_typing_analysis_defaults_to_previous_day(client, interaction_factory):
    today = dj_timezone.localdate()
    previous_day = today - timedelta(days=1)

    previous_start = datetime.combine(previous_day, datetime.min.time(), tzinfo=timezone.utc).replace(hour=10)
    older_day = today - timedelta(days=3)
    older_start = datetime.combine(older_day, datetime.min.time(), tzinfo=timezone.utc).replace(hour=10)

    interaction_factory(
        call_id_external='typing-prev-day',
        start_at=previous_start,
        end_at=previous_start + timedelta(minutes=5),
        category='retencao',
        subcategory='proposta',
        observations='observacao detalhada para o dia anterior',
    )
    interaction_factory(
        call_id_external='typing-older-day',
        start_at=older_start,
        end_at=older_start + timedelta(minutes=5),
        category='retencao',
        subcategory='proposta',
        observations='observacao detalhada de dia antigo',
    )

    response = client.get(reverse('dashboards:typing_analysis'))

    assert response.status_code == 200
    rows = response.context['typing']['table']
    assert rows
    assert all(row['occurred_on'] == previous_day for row in rows)


@pytest.mark.django_db
def test_typing_analysis_accepts_explicit_day_filter(client, interaction_factory):
    target_day = dj_timezone.localdate() - timedelta(days=4)
    target_start = datetime.combine(target_day, datetime.min.time(), tzinfo=timezone.utc).replace(hour=9)

    interaction_factory(
        call_id_external='typing-target-day',
        start_at=target_start,
        end_at=target_start + timedelta(minutes=5),
        category='retencao',
        subcategory='proposta',
        observations='observacao detalhada no dia alvo',
    )

    response = client.get(
        reverse('dashboards:typing_analysis'),
        {
            'date_preset': 'custom',
            'start_date': target_day.isoformat(),
            'end_date': target_day.isoformat(),
        },
    )

    assert response.status_code == 200
    rows = response.context['typing']['table']
    assert rows
    assert all(row['occurred_on'] == target_day for row in rows)


@pytest.mark.django_db
@override_settings(DASHBOARD_TYPING_TABLE_LIMIT=2)
def test_typing_analysis_respects_configurable_limit(interaction_factory):
    day = dj_timezone.localdate() - timedelta(days=1)
    older_day = dj_timezone.localdate() - timedelta(days=3)
    day_start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc).replace(hour=8)
    older_start = datetime.combine(older_day, datetime.min.time(), tzinfo=timezone.utc).replace(hour=8)

    for idx in range(2):
        interaction_factory(
            call_id_external=f'typing-limit-new-{idx}',
            start_at=day_start + timedelta(minutes=idx),
            end_at=day_start + timedelta(minutes=idx + 1),
            category='retencao',
            subcategory='proposta',
            observations='observacao longa para validacao de limite',
        )
    interaction_factory(
        call_id_external='typing-limit-old',
        start_at=older_start,
        end_at=older_start + timedelta(minutes=1),
        category='retencao',
        subcategory='proposta',
        observations='observacao de dia antigo',
    )

    # Periodo alargado (multi-dia): limite deve ser aplicado
    payload = build_typing_analysis_payload(
        {
            'assistant_name': '',
            'start_date': older_day,
            'end_date': day,
            'service_type_id': None,
            'churn_reason_id': None,
        }
    )

    assert payload['table_limit'] == 2
    assert len(payload['table']) == 2
    assert payload['is_limited'] is True


@pytest.mark.django_db
@override_settings(DASHBOARD_TYPING_TABLE_LIMIT=2)
def test_typing_analysis_single_day_ignores_limit(interaction_factory):
    day = dj_timezone.localdate() - timedelta(days=1)
    day_start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc).replace(hour=8)

    for idx in range(3):
        interaction_factory(
            call_id_external=f'typing-single-{idx}',
            start_at=day_start + timedelta(minutes=idx),
            end_at=day_start + timedelta(minutes=idx + 1),
            category='retencao',
            subcategory='proposta',
            observations='observacao de dia unico',
        )

    # Dia unico: limite nao deve ser aplicado
    payload = build_typing_analysis_payload(
        {
            'assistant_name': '',
            'start_date': day,
            'end_date': day,
            'service_type_id': None,
            'churn_reason_id': None,
        }
    )

    assert payload['table_limit'] is None
    assert len(payload['table']) == 3
    assert payload['is_limited'] is False
