from apps.dashboards.services.label_normalization import normalize_label


def _base_enrichment(insight: dict) -> dict:
    """Garante campos operacionais padrao para todos os insights."""
    enriched = {
        **insight,
        'summary': insight.get('summary') or insight.get('description', ''),
        'operational_interpretation': '',
        'suggested_actions': [],
        'audit_recommendation': '',
    }
    return enriched


def enrich_insight(insight: dict) -> dict:
    """Enriquece insights com leitura operacional e recomendacoes por regras simples."""
    enriched = _base_enrichment(insight)

    if not enriched.get('available', True):
        enriched['operational_interpretation'] = 'Nao existem dados suficientes para conclusao operacional fiavel no periodo.'
        return enriched

    title = enriched.get('title', '')
    value = normalize_label(enriched.get('value') or '')

    if title == 'Assistente abaixo da media':
        enriched['operational_interpretation'] = 'Desempenho abaixo da media do periodo e com potencial impacto na retencao.'
        enriched['suggested_actions'] = [
            'Auditar chamadas do periodo do assistente.',
            'Validar se foi feito diagnostico do motivo de corte.',
            'Confirmar se foram apresentadas ofertas disponiveis.',
            'Rever se houve tentativa de retencao antes do fecho.',
            'Validar qualidade e completude dos registos.',
        ]
        enriched['audit_recommendation'] = 'Priorizar chamadas do assistente abaixo da media, incluindo nao retidos e sem acao registada.'
        return enriched

    if title == 'Servico com maior nao retencao':
        enriched['operational_interpretation'] = 'Servico com maior dificuldade de retencao no periodo analisado.'
        enriched['suggested_actions'] = [
            'Auditar chamadas desse servico.',
            'Validar se existem ofertas adequadas para esse servico.',
            'Rever se a equipa conhece as opcoes disponiveis.',
            'Analisar objecoes mais frequentes do servico.',
            'Confirmar se houve diagnostico antes da proposta.',
        ]
        enriched['audit_recommendation'] = 'Priorizar chamadas do servico com maior nao retencao, sobretudo quando terminou em nao retido.'
        return enriched

    if title == 'Uso de Motivo Nao Indicado':
        enriched['operational_interpretation'] = 'Existe excesso de chamadas com motivo generico e baixa utilidade analitica.'
        enriched['suggested_actions'] = [
            'Auditar amostra de chamadas com motivo nao indicado.',
            'Reforcar o preenchimento correto de third_category na operacao.',
            'Verificar se a causa raiz e processo, sistema ou formacao.',
            'Validar qualidade do registo operacional.',
        ]
        enriched['audit_recommendation'] = 'Priorizar chamadas com motivo nao indicado para recuperar a tipificacao correta.'
        return enriched

    if title == 'Total de inconsistencias':
        enriched['operational_interpretation'] = 'Existem registos potencialmente incorretos ou incompletos no periodo.'
        enriched['suggested_actions'] = [
            'Rever preenchimento dos campos obrigatorios.',
            'Auditar amostra de chamadas inconsistentes.',
            'Confirmar se a regra operacional esta clara para a equipa.',
            'Identificar se o problema e de processo ou de formacao.',
        ]
        enriched['audit_recommendation'] = 'Priorizar chamadas marcadas como inconsistentes e cruzar com os respetivos registos de resultado.'
        return enriched

    if title == 'Motivo com menor taxa de retencao':
        enriched['operational_interpretation'] = 'Motivo com pior desempenho de retencao no periodo.'
        enriched['suggested_actions'] = [
            'Auditar chamadas desse motivo de corte.',
            'Validar se existe argumentario adequado para a objecao.',
            'Confirmar se existem ofertas competitivas para este contexto.',
            'Rever se a objecao esta a ser bem trabalhada.',
        ]
        enriched['audit_recommendation'] = 'Priorizar chamadas do motivo com menor retencao para confirmar diagnostico e proposta.'
        return enriched

    if title == 'Motivos criticos sem retencao':
        enriched['operational_interpretation'] = 'Existem motivos recorrentes com 0% de retencao e risco elevado de perda.'
        enriched['suggested_actions'] = [
            'Priorizar auditoria imediata dos motivos listados.',
            'Definir argumentario especifico por motivo critico.',
            'Reforcar formacao de contorno para os cenarios mais frequentes.',
        ]
        enriched['audit_recommendation'] = 'Priorizar chamadas dos motivos criticos sem retencao para plano de acao corretivo.'
        return enriched

    if title == 'Assistente com mais inconsistencias':
        enriched['operational_interpretation'] = 'Concentracao de inconsistencias num assistente acima do esperado.'
        enriched['suggested_actions'] = [
            'Auditar amostra das chamadas inconsistentes desse assistente.',
            'Validar entendimento das regras de preenchimento.',
            'Reforcar feedback operacional individual.',
        ]
        enriched['audit_recommendation'] = 'Priorizar chamadas inconsistentes do assistente identificado para calibrar qualidade de registo.'
        return enriched

    enriched['operational_interpretation'] = 'Insight informativo para monitorizacao de desempenho no periodo.'
    return enriched
