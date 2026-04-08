from apps.dashboards.services.label_normalization import normalize_label
from apps.dashboards.services.previous_day import _is_no_action_label
from apps.dashboards.services.previous_day import _is_not_retained_outcome


def test_normalize_label_handles_accents_and_spaces():
    assert normalize_label(' Não   retido ') == 'nao retido'
    assert normalize_label(' Sem ação ') == 'sem acao'


def test_outcome_equivalence_nao_retido_variants():
    assert _is_not_retained_outcome('Nao Retido') is True
    assert _is_not_retained_outcome('Não retido') is True


def test_no_action_equivalence_sem_acao_variants():
    assert _is_no_action_label('Sem acao') is True
    assert _is_no_action_label('Sem ação') is True


def test_configurable_no_action_aliases():
    assert _is_no_action_label('Sem acao registada') is True
    assert _is_no_action_label('Pendente') is False
