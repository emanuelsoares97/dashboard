"""
Palavras-chave suplementares para conceitos conhecidos do domínio de retenção.
As chaves são fragmentos normalizados do third_category (sem acentos, minúsculas).
Os valores são palavras adicionais que reforçam o reconhecimento desse tipo.
O loader adiciona estas palavras às extraídas automaticamente do xlsx.
"""

DOMAIN_BOOST: dict[str, list[str]] = {
    # Cancelamento / churn
    'cancelamento': ['cancelar', 'cancela', 'encerrar', 'encerrando', 'sair', 'terminar', 'deixar', 'desistir'],
    'cancel': ['cancelar', 'cancela', 'encerrar', 'sair'],
    # Retenção
    'retencao': ['reter', 'manter', 'continuar', 'ficar', 'proposta', 'oferta', 'desconto'],
    'retencao voluntaria': ['optou', 'aceitou', 'convencido', 'decidiu ficar'],
    # Preço
    'preco': ['caro', 'valor', 'custo', 'preco', 'taxa', 'cobranca', 'mensalidade', 'fatura', 'conta'],
    'fatura': ['fatura', 'cobranca', 'debito', 'pagamento', 'valor cobrado'],
    # Qualidade de serviço
    'qualidade': ['lento', 'instavel', 'falha', 'queda', 'interrupcao', 'problema', 'nao funciona'],
    'tecnico': ['tecnico', 'avaria', 'equipamento', 'router', 'modem', 'sinal', 'velocidade'],
    # Concorrência
    'concorrencia': ['concorrente', 'outra operadora', 'proposta melhor', 'vieram propor'],
    'portabilidade': ['portar', 'transferir', 'mudar', 'outra empresa'],
    # Contrato
    'contrato': ['fidelizacao', 'vinculo', 'compromisso', 'prazo', 'renovar'],
    'upgrade': ['upgrade', 'melhorar', 'subir', 'aumentar', 'adicionar'],
    'downgrade': ['downgrade', 'reduzir', 'baixar', 'diminuir', 'simplificar'],
    # Call drop
    'call drop': ['chamada caiu', 'ligacao cortou', 'sem resposta', 'nao atendeu'],
    # Resolvido
    'resolvido': ['resolvido', 'solucionado', 'satisfeito', 'aceite', 'concordou', 'ok'],
    # Mudança de residência
    'mudanca': ['mudar', 'muda', 'outro local', 'outro pais', 'emigrar', 'outro endereco'],
    # Falecimento / incapacidade
    'falecimento': ['falecimento', 'faleceu', 'obito', 'morte', 'viuvez'],
    # Insatisfação
    'insatisfeito': ['insatisfeito', 'descontente', 'irritado', 'chateado', 'decepcionado', 'mau atendimento'],
}


def get_boost_keywords(third_category_normalized: str) -> list[str]:
    """Devolve palavras-chave de reforço para a tipificação, se disponíveis."""
    for key, kws in DOMAIN_BOOST.items():
        if key in third_category_normalized:
            return kws
    return []
