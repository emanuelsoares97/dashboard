import hashlib
from typing import Any

import pandas as pd
from django.utils.text import slugify

from apps.imports_app.types import ImportRowData


SERVICE_TYPE_NORMALIZATION_MAP = {
    'Voz p\u00f3s-paga': 'Voz p\u00f3s-pago',
    'Voz pr\u00e9-paga': 'Voz pr\u00e9-pago',
    'Voz p\u00c3\u00b3s-paga': 'Voz p\u00f3s-pago',
    'Voz pr\u00c3\u00a9-paga': 'Voz pr\u00e9-pago',
}

CALL_DROP_VALUES = {
    'chamada_caiu',
    'call_drop',
    'call_dropped',
    'chamada_em_silencio',
    'contact_failed',
    'contacto_sem_sucesso',
    'ausencia_de_processo',
    'no_process',
}

PENDING_VALUES = {
    'pendente',
    'pending',
}

NOT_RETAINED_VALUES = {
    'nao_retido',
    'nao_retida',
    'not_retained',
    'nao_aceita_resolucao',
    'resolution_not_accepted',
    'nao_fez_contrato',
}

FORWARDED_VALUES = {
    'encaminhado_email_ticket',
    'ticket_forwarded',
    'dados_de_pagamento',
    'payment_details',
    'iban_payment_details',
    'correccao_de_email',
    'correcao_de_email',
    'email_correction',
    'contacto_tlm_email_de_comercial',
    'email_contact_tlm',
}

RESOLVED_OUTSIDE_RETENTION_VALUES = {
    'resolved',
    'resolvido',
    'rezolvat',
    'cliente_teste',
    'test_client',
}

RETENTION_CATEGORY_EXACT_VALUES = {
    'retencao',
}

RETENTION_CATEGORY_PREFIXES = (
    'cc ret ',
)


def normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ''
    return str(value).strip()


def to_bool(value: Any) -> bool:
    text = normalize_text(value).lower()
    return text in {'1', 'true', 'sim', 'yes', 'call drop'}


def parse_datetime(value: Any):
    if pd.isna(value) or value in (None, ''):
        return None

    try:
        return pd.to_datetime(value).to_pydatetime()
    except (TypeError, ValueError):
        return None


def build_raw_payload(row: dict[str, Any]) -> dict[str, str]:
    return {column: normalize_text(value) for column, value in row.items()}


def build_raw_hash(raw_payload: dict[str, str]) -> str:
    normalized_items = sorted((str(key), str(value)) for key, value in raw_payload.items())
    serialized = '|'.join(f'{key}={value}' for key, value in normalized_items)
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


def normalize_service_type(value: Any) -> str:
    service_type = normalize_text(value)
    return SERVICE_TYPE_NORMALIZATION_MAP.get(service_type, service_type)


def is_retention_category(value: Any) -> bool:
    normalized = slugify(normalize_text(value)).replace('-', '_')
    if not normalized:
        return False
    if normalized in RETENTION_CATEGORY_EXACT_VALUES:
        return True
    return any(normalized.startswith(prefix.replace(' ', '_')) for prefix in RETENTION_CATEGORY_PREFIXES)


def normalize_ret_resolution(value: Any, *, is_retention_case: bool) -> str:
    normalized = normalize_text(value)
    normalized_code = slugify(normalized).replace('-', '_')

    if not normalized_code:
        return ''
    if normalized_code in CALL_DROP_VALUES:
        return 'Call Drop'
    if not is_retention_case:
        if normalized_code.startswith('transferencia_para') or normalized_code.startswith('transfer_to_') or normalized_code in FORWARDED_VALUES:
            return 'Encaminhado'
        if normalized_code in PENDING_VALUES:
            return 'Pendente'
        return 'Resolvido fora de retencao'
    if normalized_code in PENDING_VALUES:
        return 'Pendente'
    if normalized_code in NOT_RETAINED_VALUES:
        return 'Nao Retido'
    if normalized_code in {'retido', 'retained', 'anulacao_do_pedido_de_corte'} or normalized_code.startswith('retido_'):
        return 'Retido'
    if normalized_code.startswith('transferencia_para') or normalized_code.startswith('transfer_to_') or normalized_code in FORWARDED_VALUES:
        return 'Encaminhado'
    if normalized_code in RESOLVED_OUTSIDE_RETENTION_VALUES:
        return 'Resolvido fora de retencao'
    return 'Resolvido fora de retencao'


def map_row(row_number: int, row: dict[str, Any]) -> ImportRowData:
    raw_payload = build_raw_payload(row)
    retention_action = normalize_text(row.get('retention_action'))
    category = normalize_text(row.get('category'))
    final_outcome = normalize_ret_resolution(
        row.get('final_outcome') or retention_action,
        is_retention_case=is_retention_category(category),
    )

    return ImportRowData(
        row_number=row_number,
        raw_payload=raw_payload,
        external_call_id=normalize_text(row.get('external_call_id')),
        agent_name=normalize_text(row.get('agent_name')),
        start_at=parse_datetime(row.get('start_date')),
        end_at=parse_datetime(row.get('end_date')),
        final_outcome=final_outcome,
        retention_action=retention_action,
        churn_reason=normalize_text(row.get('churn_reason')),
        service_type=normalize_service_type(row.get('service_type')),
        is_call_drop=final_outcome == 'Call Drop',
        day=normalize_text(row.get('day')),
        week=normalize_text(row.get('week')),
        month=normalize_text(row.get('month')),
        exclude=normalize_text(row.get('exclude')),
        category=category,
        subcategory=normalize_text(row.get('subcategory')),
        observations=normalize_text(row.get('observations')),
    )
