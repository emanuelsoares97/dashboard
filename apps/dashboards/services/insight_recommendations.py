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
    value = (enriched.get('value') or '').strip().lower()

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

    if title == 'Acao mais utilizada' and value in {'sem acao', 'pendente'}:
        enriched['operational_interpretation'] = 'Elevado volume de chamadas sem acao de retencao registada.'
        enriched['suggested_actions'] = [
            'Validar se sem acao esta a ser usado corretamente.',
            'Confirmar se existiam ofertas aplicaveis.',
            'Auditar amostra de chamadas sem acao registada.',
            'Rever se faltou diagnostico do motivo de corte.',
            'Validar qualidade do registo operacional.',
        ]
        enriched['audit_recommendation'] = 'Priorizar chamadas com acao sem acao para verificar se era devido encetar tentativa de retencao.'
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

    if title == 'Pior motivo de corte':
        enriched['operational_interpretation'] = 'Motivo com pior desempenho de retencao no periodo.'
        enriched['suggested_actions'] = [
            'Auditar chamadas desse motivo de corte.',
            'Validar se existe argumentario adequado para a objecao.',
            'Confirmar se existem ofertas competitivas para este contexto.',
            'Rever se a objecao esta a ser bem trabalhada.',
        ]
        enriched['audit_recommendation'] = 'Priorizar chamadas do pior motivo de corte para confirmar diagnostico, proposta e tentativa de fecho.'
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
