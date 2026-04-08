"""Testes ao motor de validação de tipificações."""

import pytest

from apps.dashboards.typing_analysis.normalizer import extract_keywords
from apps.dashboards.typing_analysis.normalizer import normalize_text
from apps.dashboards.typing_analysis.normalizer import repair_text_encoding
from apps.dashboards.typing_analysis.loader import TypificationDefinition
from apps.dashboards.typing_analysis.scorer import (
    score_typification,
    score_all,
    ScoreBreakdown,
)
from apps.dashboards.typing_analysis.validator import (
    validate,
    STATUS_BLANK_TYPIFICATION,
    STATUS_CORRECT,
    STATUS_LIKELY_CORRECT,
    STATUS_NEEDS_REVIEW,
    STATUS_LIKELY_INCORRECT,
    STATUS_INSUFFICIENT,
    STATUS_EMPTY,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def cancelamento_defn():
    return TypificationDefinition(
        category='cancelamento',
        subcategory='pedido do cliente',
        third_category='cancelamento voluntario',
        utilizacao='cliente solicita cancela servico',
        keywords=['cancelar', 'cancelamento', 'cancela', 'sair', 'encerrar', 'servico'],
        negative_keywords=['retido', 'ficou', 'aceitou'],
        patterns=[r'quer\s+cancel', r'pede\s+cancel'],
    )


@pytest.fixture()
def retencao_defn():
    return TypificationDefinition(
        category='retencao',
        subcategory='proposta aceite',
        third_category='retencao com desconto',
        utilizacao='cliente aceitou proposta de retencao com desconto',
        keywords=['retido', 'desconto', 'oferta', 'aceitou', 'ficou', 'proposta'],
        negative_keywords=['cancelar', 'sair'],
        patterns=[r'aceitou\s+proposta', r'ficou\s+com'],
    )


@pytest.fixture()
def definitions(cancelamento_defn, retencao_defn):
    return (cancelamento_defn, retencao_defn)


# ── Normalizador ─────────────────────────────────────────────────────────────

class TestNormalizer:
    def test_removes_accents(self):
        assert normalize_text('cancelação') == 'cancelacao'

    def test_lowercases(self):
        assert normalize_text('CANCELAMENTO') == 'cancelamento'

    def test_strips_punctuation(self):
        assert normalize_text('ok, tudo bem!') == 'ok tudo bem'

    def test_collapses_whitespace(self):
        assert normalize_text('  dois   espacos  ') == 'dois espacos'

    def test_none_returns_empty(self):
        assert normalize_text(None) == ''

    def test_extract_keywords_removes_stopwords(self):
        kws = extract_keywords('cancelamento de servico')
        assert 'de' not in kws
        assert 'cancelamento' in kws
        assert 'servico' in kws

    def test_repairs_common_mojibake_examples(self):
        raw = 'RetenÃ§Ã£o de serviÃ§os nÃ£o essenciais em cartÃµes e informaÃ§Ã£o mÃ³vel'
        repaired = repair_text_encoding(raw)

        assert 'Retenção' in repaired
        assert 'serviços' in repaired
        assert 'não' in repaired
        assert 'cartões' in repaired
        assert 'informação' in repaired
        assert 'móvel' in repaired

    def test_normalize_text_handles_mojibake_and_accents(self):
        raw = 'RetenÃ§Ã£o de serviÃ§os nÃ£o essenciais em cartÃµes; atualização e operação.'

        assert normalize_text(raw) == 'retencao de servicos nao essenciais em cartoes atualizacao e operacao'


# ── Pontuação ────────────────────────────────────────────────────────────────

class TestScorer:
    def test_high_score_for_matching_observation(self, cancelamento_defn):
        obs = 'cliente quer cancelar o servico nao quer mais ficar'
        score = score_typification(normalize_text(obs), cancelamento_defn)
        assert isinstance(score, ScoreBreakdown)
        assert score.total > 0.4

    def test_low_score_for_unrelated_observation(self, cancelamento_defn):
        obs = 'cliente ficou muito satisfeito e aceitou a proposta de desconto'
        score = score_typification(normalize_text(obs), cancelamento_defn)
        assert score.total < 0.6  # palavras-chave negativas devem penalizar

    def test_score_all_returns_sorted_list(self, definitions):
        obs = normalize_text('cliente pediu cancelamento imediato quer sair do contrato')
        ranked = score_all(obs, definitions)
        assert len(ranked) == 2
        assert ranked[0].score.total >= ranked[1].score.total

    def test_score_all_empty_definitions(self):
        ranked = score_all('qualquer coisa', ())
        assert ranked == []

    def test_structure_score_rewards_length(self, cancelamento_defn):
        short_obs = normalize_text('cancelar')
        long_obs = normalize_text(
            'cliente ligou pedindo cancelamento pois nao esta satisfeito com o servico e quer sair'
        )
        short_score = score_typification(short_obs, cancelamento_defn)
        long_score = score_typification(long_obs, cancelamento_defn)
        assert long_score.structure > short_score.structure


# ── Validador ────────────────────────────────────────────────────────────────

class TestValidator:
    def test_empty_observation_returns_empty_status(self, definitions):
        result = validate('', 'cancelamento', 'pedido do cliente', 'cancelamento voluntario',
                          definitions=definitions)
        assert result.status == STATUS_EMPTY

    def test_whitespace_only_observation_returns_empty(self, definitions):
        result = validate('   ', 'cancelamento', 'pedido do cliente', 'cancelamento voluntario',
                          definitions=definitions)
        assert result.status == STATUS_EMPTY

    def test_very_short_observation_returns_insufficient(self, definitions):
        result = validate('ok', 'cancelamento', 'pedido do cliente', 'cancelamento voluntario',
                          definitions=definitions)
        assert result.status == STATUS_INSUFFICIENT

    def test_missing_any_typification_level_returns_blank_typification(self, definitions):
        result = validate(
            'cliente quer cancelar o servico e pede encerramento ainda hoje',
            'cancelamento',
            '',
            'cancelamento voluntario',
            definitions=definitions,
        )
        assert result.status == STATUS_BLANK_TYPIFICATION

    def test_well_aligned_returns_correct_or_likely(self, definitions):
        obs = 'cliente quer cancelar servico pede cancelamento imediato pois vai sair'
        result = validate(
            obs,
            'cancelamento',
            'pedido do cliente',
            'cancelamento voluntario',
            definitions=definitions,
        )
        assert result.status in (STATUS_CORRECT, STATUS_LIKELY_CORRECT)

    def test_misaligned_returns_incorrect(self, definitions):
        # Observação fala de retenção mas tipificação diz cancelamento
        obs = 'cliente aceitou a proposta de desconto ficou retido satisfeito com oferta'
        result = validate(
            obs,
            'cancelamento',
            'pedido do cliente',
            'cancelamento voluntario',
            definitions=definitions,
        )
        assert result.status in (STATUS_LIKELY_INCORRECT, STATUS_NEEDS_REVIEW)

    def test_unrecognised_tipification(self, definitions):
        obs = 'cliente ligou para reclamar de uma situacao estranha que aconteceu'
        result = validate(
            obs,
            'desconhecido',
            'desconhecido',
            'tipificacao que nao existe no ficheiro',
            definitions=definitions,
        )
        # Should still return a result, not raise
        assert result.status in (STATUS_LIKELY_INCORRECT, STATUS_NEEDS_REVIEW, STATUS_CORRECT, STATUS_LIKELY_CORRECT)
        assert 'não reconhecida' in result.reason

    def test_no_definitions_returns_needs_review(self):
        result = validate(
            'teste de observacao suficientemente longa para analise aqui',
            'cat',
            'sub',
            'third',
            definitions=(),
        )
        assert result.status == STATUS_NEEDS_REVIEW

    def test_result_has_all_required_fields(self, definitions):
        result = validate(
            'cliente pretende cancelar o contrato de telecomunicacoes nao quer continuar',
            'cancelamento',
            'pedido do cliente',
            'cancelamento voluntario',
            definitions=definitions,
        )
        assert result.status_label
        assert result.status_css
        assert isinstance(result.used_score, float)
        assert isinstance(result.best_score, float)
        assert isinstance(result.delta, float)
        assert result.reason
