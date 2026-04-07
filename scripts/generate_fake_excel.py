from __future__ import annotations

import argparse
import calendar
import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


# --------------------------------------------------------------------------- #
# Tipificações reais baseadas em tip_descricao.xlsx                           #
# Cada entrada define categoria, subcategoria, motivo (third_category) e      #
# dois conjuntos de observações: alinhadas (corretas) e desalinhadas (erradas) #
# --------------------------------------------------------------------------- #

TIPIFICATIONS: list[dict] = [
    {
        'category': 'cc ret pedido de desativacao',
        'subcategory': 'cc ret movel',
        'third_category': 'concorrencia',
        'correct': [
            "Cliente informa que recebeu uma proposta da concorrência com preço mais baixo e quer cancelar.",
            "Outra operadora fez uma oferta com mais dados e menor mensalidade. Cliente quer mudar.",
            "Vieram à porta de casa propor contrato com operadora concorrente.",
            "A concorrência está a oferecer o dobro da velocidade pelo mesmo preço.",
            "Recebeu proposta da concorrência via SMS com condições muito vantajosas.",
            "Empresa concorrente contactou o cliente com oferta personalizada mais barata.",
        ],
        'incorrect': [
            "Cliente ficou retido após aceitar proposta de desconto de 15% durante 6 meses.",
            "Problema no router de fibra em casa, sem sinal desde ontem.",
            "Ficou desempregado há dois meses e não consegue pagar a mensalidade.",
            "Vai emigrar por mais de um ano, não necessita do serviço actualmente.",
            "Falecimento do titular, família quer encerrar todos os contratos.",
        ],
    },
    {
        'category': 'cc ret pedido de desativacao',
        'subcategory': 'cc ret movel',
        'third_category': 'dif financeiras',
        'correct': [
            "Cliente em situação financeira difícil, não consegue pagar a mensalidade.",
            "Ficou desempregado e precisa de reduzir despesas fixas urgentemente.",
            "Situação económica muito complicada, corte de salário obriga a cancelar.",
            "Cliente perdeu o emprego há um mês e não consegue suportar o custo do contrato.",
            "Dificuldades económicas sérias, pediu cancelamento para baixar custos mensais.",
            "Reforma antecipada com redução de rendimento, não consegue manter o serviço.",
        ],
        'incorrect': [
            "Proposta da concorrência com mais dados pelo mesmo preço.",
            "Problema técnico intermitente no móvel, vários tickets abertos sem resolução.",
            "Mudança de morada para zona sem cobertura da rede.",
            "Cliente ficou satisfeito e aceitou proposta de retenção com desconto.",
            "Insatisfeito com o atendimento, foi mal tratado na última chamada.",
        ],
    },
    {
        'category': 'cc ret pedido de desativacao',
        'subcategory': 'cc ret fibra',
        'third_category': 'problema tecnico fibra',
        'correct': [
            "Problema de velocidade na fibra há mais de duas semanas, técnico já veio mas não resolveu.",
            "Internet cai constantemente à noite, vários tickets abertos sem solução definitiva.",
            "Router da fibra perde sinal repetidamente, serviço completamente instável.",
            "Queda de ligação frequente na fibra, cliente muito insatisfeito com a situação.",
            "Velocidade muito abaixo do contratado, cliente tem comprovativo dos testes.",
            "Desde a última visita técnica a fibra continua instável e sem resolução.",
        ],
        'incorrect': [
            "Recebeu proposta da concorrência com melhores condições de preço.",
            "Dificuldades financeiras, não consegue pagar as despesas fixas.",
            "Retido com sucesso após proposta de upgrade de velocidade sem custo.",
            "Cliente ausente por longa temporada no estrangeiro.",
            "Fatura com cobrança indevida, cliente quer encerrar o contrato.",
        ],
    },
    {
        'category': 'cc ret pedido de desativacao',
        'subcategory': 'cc ret fibra',
        'third_category': 'problema faturacao',
        'correct': [
            "Cliente recebeu fatura com valor superior ao contratado e quer cancelar.",
            "Cobrança indevida na última fatura, já reclamou mas não foi resolvido.",
            "Fatura com serviços que nunca pediu, exige encerrar o contrato.",
            "Débito automático com valor errado este mês, cliente muito indignado.",
            "Taxa não prevista no contrato foi cobrada na fatura de Março.",
            "Fatura duplicada este mês, sem resposta satisfatória do apoio ao cliente.",
        ],
        'incorrect': [
            "Problemas técnicos frequentes na fibra, ligação instável há semanas.",
            "Recebeu proposta da concorrência e quer mudar de operadora.",
            "Mudança de morada para zona sem cobertura disponível.",
            "Dificuldades financeiras, perdeu o emprego recentemente.",
        ],
    },
    {
        'category': 'cc ret pedido de desativacao',
        'subcategory': 'cc ret fibra',
        'third_category': 'insatisfacao com o atendimento',
        'correct': [
            "Cliente muito insatisfeito com o atendimento, foi mal tratado na última chamada.",
            "Experiência muito negativa no contacto anterior, atendente foi rude e ineficaz.",
            "Mau atendimento em loja, cliente sente-se completamente desrespeitado.",
            "Vários contactos sem resolução, cliente farto do mau serviço de apoio.",
            "Atendimento muito abaixo do esperado, as queixas nunca são resolvidas.",
        ],
        'incorrect': [
            "Problema técnico intermitente na fibra há semanas.",
            "Proposta da concorrência com condições mais vantajosas.",
            "Dificuldades financeiras, perdeu o emprego.",
            "Nova morada sem cobertura de fibra disponível.",
        ],
    },
    {
        'category': 'cc ret pedido de desativacao',
        'subcategory': 'cc ret fibra',
        'third_category': 'nova morada sem cobertura',
        'correct': [
            "Cliente vai mudar de morada para zona rural sem cobertura de fibra disponível.",
            "Nova residência fica em área onde o serviço não está disponível.",
            "Mudança para localidade onde a operadora não tem cobertura.",
            "Nova morada não tem infraestrutura de fibra, impossível manter o contrato.",
            "Transferência para local onde o serviço de fibra não chega.",
        ],
        'incorrect': [
            "Proposta da concorrência com preço mais baixo.",
            "Dificuldades financeiras, não consegue pagar.",
            "Problema técnico persiste há semanas sem resolução.",
            "Insatisfeito com o atendimento recebido.",
        ],
    },
    {
        'category': 'cc ret pedido de desativacao',
        'subcategory': 'cc ret movel',
        'third_category': 'falta de cobertura movel',
        'correct': [
            "Cobertura de rede muito fraca na zona de residência, serviço inutilizável.",
            "Sem sinal na área de trabalho do cliente, situação totalmente inaceitável.",
            "Rede móvel com cobertura precária no local onde o cliente passa mais tempo.",
            "Cliente sem rede em casa e no trabalho, impossível usar o serviço.",
            "Cobertura completamente insuficiente na localidade onde reside.",
        ],
        'incorrect': [
            "Proposta da concorrência com mais dados e menor valor mensal.",
            "Dificuldades financeiras, salário foi reduzido recentemente.",
            "Cliente ficou retido com novo plano de dados ilimitados.",
            "Fatura com cobrança indevida, quer cancelar por isso.",
        ],
    },
    {
        'category': 'cc ret pedido de desativacao',
        'subcategory': 'cc ret movel',
        'third_category': 'falecimento do titular',
        'correct': [
            "Familiar informa que o titular do contrato faleceu, pretende encerrar o serviço.",
            "Falecimento do titular, cônjuge ligou para cancelar todos os serviços activos.",
            "Cliente faleceu, filho está a tratar do encerramento dos contratos.",
            "Óbito do titular confirmado pelo familiar, solicitam cancelamento imediato.",
        ],
        'incorrect': [
            "Proposta da concorrência, quer mudar de operadora.",
            "Problemas técnicos intermitentes sem resolução após vários tickets.",
            "Dificuldades financeiras, reduziu rendimento.",
        ],
    },
    {
        'category': 'cc ret pedido de desativacao',
        'subcategory': 'cc ret movel',
        'third_category': 'ausencia prolongada',
        'correct': [
            "Cliente vai emigrar e ficará fora do país por período prolongado.",
            "Ausência no estrangeiro por motivos profissionais durante vários meses.",
            "Vai para o exterior por mais de um ano, não necessita do serviço.",
            "Transferência de trabalho para o estrangeiro por prazo indefinido.",
            "Vai morar fora do país durante pelo menos dois anos.",
        ],
        'incorrect': [
            "Proposta da concorrência mais económica, quer mudar.",
            "Problema técnico na rede móvel sem resolução.",
            "Dificuldades financeiras urgentes.",
            "Fatura com erro de cobrança.",
        ],
    },
    {
        'category': 'cc ret pedido de desativacao',
        'subcategory': 'cc ret fibra',
        'third_category': 'retencao fibra',
        'correct': [
            "Cliente retido após aceitar proposta de desconto de 20% na fibra durante um ano.",
            "Retido com sucesso, aceitou upgrade de velocidade sem custo adicional.",
            "Proposta de fidelização aceite, cliente mantém a fibra com nova oferta.",
            "Cliente convencido a ficar com desconto de 15 euros mensais.",
            "Ficou satisfeito com a contraoferta e decidiu continuar com o serviço.",
            "Aceite oferta de fibra com velocidade superior pelo mesmo preço.",
        ],
        'incorrect': [
            "Problemas técnicos frequentes na fibra, ainda por resolver.",
            "Proposta da concorrência, quer mudar de operadora.",
            "Dificuldades financeiras graves.",
            "Fatura com valor errado este mês.",
        ],
    },
    {
        'category': 'cc ret pedido de desativacao',
        'subcategory': 'cc ret movel',
        'third_category': 'retencao movel',
        'correct': [
            "Cliente retido com proposta de mais dados pelo mesmo valor mensal.",
            "Aceitou upgrade de plano, ficou satisfeito e mantém o contrato.",
            "Retido após desconto de 10 euros mensais durante 6 meses.",
            "Nova proposta aceite, continuará com o serviço móvel.",
            "Cliente retido após oferta de dados ilimitados com ligeiro aumento de preço.",
        ],
        'incorrect': [
            "Recebeu proposta da concorrência e quer mesmo mudar.",
            "Em dificuldades financeiras, precisa cortar despesas fixas.",
            "Problema de cobertura na nova zona de residência.",
            "Fatura com erros repetidos, quer cancelar.",
        ],
    },
    {
        'category': 'cc ret pedido de desativacao',
        'subcategory': 'cc ret movel',
        'third_category': 'motivo nao indicado',
        'correct': [
            "Cliente não quis indicar o motivo do cancelamento.",
            "Recusou-se a explicar a razão do pedido de cancelamento.",
            "Não foi possível apurar o motivo, cliente não colaborou.",
            "Apenas diz que quer cancelar, sem dar mais qualquer informação.",
        ],
        'incorrect': [
            "Proposta da concorrência com preço mais baixo.",
            "Dificuldades financeiras, não consegue pagar.",
            "Problema técnico na fibra há semanas.",
            "Insatisfeito com o atendimento recebido.",
        ],
    },
    {
        'category': 'cc ret pedido de desativacao',
        'subcategory': 'cc ret fibra',
        'third_category': 'reputacao do servico',
        'correct': [
            "Cliente ouviu muitas reclamações sobre a operadora e perdeu a confiança no serviço.",
            "Má reputação da empresa foi o principal motivo referido pelo cliente.",
            "Viu muitas reclamações nas redes sociais e decidiu cancelar o contrato.",
            "Imagem muito negativa da operadora junto de amigos levou cliente a querer sair.",
        ],
        'incorrect': [
            "Problema técnico persistente, vários tickets abertos sem resposta.",
            "Proposta da concorrência mais barata.",
            "Dificuldades financeiras.",
        ],
    },
    {
        'category': 'cc ret pedido de desativacao',
        'subcategory': 'cc ret movel',
        'third_category': 'segunda residencia',
        'correct': [
            "Cliente tem segunda residência e vai lá passar a maior parte do tempo.",
            "Vai instalar o serviço na segunda residência com outra operadora local.",
            "Segunda habitação onde fica a maior parte do ano não tem cobertura.",
            "Muda-se em definitivo para segunda habitação onde o serviço não está disponível.",
        ],
        'incorrect': [
            "Proposta da concorrência com melhores condições de preço.",
            "Problema técnico persistente sem resolução.",
            "Dificuldades financeiras sérias.",
        ],
    },
    {
        'category': 'cc ret pedido de desativacao',
        'subcategory': 'cc ret fibra',
        'third_category': 'problema tecnico tv',
        'correct': [
            "Problemas constantes com o serviço de TV, canais a bloquear e imagem pixelizada.",
            "TV por cabo com falhas frequentes, imagem cor de rosa em vários canais.",
            "Box de TV a reiniciar sozinha várias vezes por semana.",
            "Serviço de TV com interrupções diárias, técnico já veio mas não resolveu.",
            "Canais a congelar frequentemente, especialmente nas horas de maior afluência.",
        ],
        'incorrect': [
            "Proposta da concorrência com preço mais baixo.",
            "Dificuldades financeiras.",
            "Problema técnico na fibra.",
            "Cliente aceitou retenção e ficou satisfeito.",
        ],
    },
    {
        'category': 'cc ret pedido de desativacao',
        'subcategory': 'cc ret movel',
        'third_category': 'chamada caiu ou cliente desliga',
        'correct': [
            "A chamada caiu antes de ser possível concluir o atendimento.",
            "Cliente desligou sem que houvesse resolução da situação.",
            "Ligação interrompida a meio da conversa.",
            "Não foi possível concluir o atendimento, chamada cortou de repente.",
        ],
        'incorrect': [
            "Cliente explicou em detalhe o problema técnico que tem na fibra.",
            "Recebeu proposta da concorrência e está a considerar aceitar.",
        ],
    },
    {
        'category': 'cc ret pedido de desativacao',
        'subcategory': 'cc ret fibra',
        'third_category': 'nova morada concorrencia',
        'correct': [
            "Mudança de morada para zona onde a concorrência tem melhor cobertura.",
            "Nova morada já tem contrato com operadora concorrente instalado.",
            "Cliente vai para nova morada onde a concorrência já fez oferta antecipada.",
            "Nova residência e concorrência já contactou a família com proposta.",
        ],
        'incorrect': [
            "Dificuldades financeiras graves.",
            "Problema técnico na fibra.",
            "Insatisfeito com o atendimento.",
        ],
    },
    {
        'category': 'cc ret pedido de desativacao',
        'subcategory': 'cc ret movel',
        'third_category': 'nao atende',
        'correct': [
            "Tentou-se contactar o cliente mas não atendeu a chamada.",
            "Canal não estabelecido, cliente não atendeu após três tentativas.",
            "Sem contacto, cliente não atende nos números registados.",
        ],
        'incorrect': [
            "Proposta da concorrência, quer mudar.",
            "Dificuldades financeiras.",
            "Problema técnico na rede.",
        ],
    },
]

# Observações vagas que não permitem concluir sobre a tipificação (cenário ambíguo)
_VAGUE_OBSERVATIONS = [
    "Cliente contactou a empresa para tratar do assunto.",
    "Pedido registado conforme solicitado.",
    "Situação analisada, aguarda resposta.",
    "Ok.",
    "Cliente informado dos procedimentos.",
    "Processo em curso.",
    "Aguarda validação interna.",
    "Situação tratada conforme procedimento interno.",
    "Registado.",
    "Contacto efectuado.",
]


def _pick_observation(tip: dict, scenario: str) -> str:
    """Selecciona uma observação com base no cenário escolhido para a linha."""
    if scenario == 'correct':
        return random.choice(tip['correct'])
    if scenario == 'wrong':
        # Usa a observação correcta de uma tipificação diferente → desalinhamento claro
        wrong_tip = random.choice([t for t in TIPIFICATIONS if t['third_category'] != tip['third_category']])
        return random.choice(wrong_tip['correct'])
    if scenario == 'empty':
        return ''
    # ambiguous
    return random.choice(_VAGUE_OBSERVATIONS)


def random_datetime_in_month(year: int, month: int) -> datetime:
    last_day = calendar.monthrange(year, month)[1]
    day = random.randint(1, last_day)
    hour = random.randint(8, 19)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return datetime(year, month, day, hour, minute, second)


# 10 assistentes fixos — os mesmos em todos os meses
_ASSISTANT_NAMES = [
    "Ana Ribeiro",
    "Bruno Costa",
    "Carla Mendes",
    "Diogo Almeida",
    "Elisa Martins",
    "Fabio Sousa",
    "Gabriela Rocha",
    "Henrique Pinto",
    "Ines Silva",
    "Joao Nunes",
]

_SERVICE_TYPES = [
    "Fibra",
    "Movel",
    "Voz pos-pago",
    "Voz pre-pago",
    "TV + Net",
]

_RETENTION_ACTIONS = [
    "Desconto",
    "Upgrade",
    "Fidelizacao",
    "Oferta adicional",
    "Pendente",
    "Sem acao",
]

_OUTCOMES = ["Retido", "Nao Retido", "Call Drop"]
_OUTCOME_WEIGHTS = [0.36, 0.58, 0.06]

# Distribuição dos cenários de observação:
#   correct → observação alinhada com a tipificação (deve classificar como correto/provável correto)
#   wrong   → observação claramente de outra tipificação (deve classificar como provável incorreto)
#   vague   → observação ambígua/curta (deve classificar como requer revisão)
#   empty   → sem observação (contabilizado como vazio nos KPIs)
_SCENARIOS = ['correct', 'correct', 'correct', 'wrong', 'wrong', 'vague', 'empty']
_SCENARIO_WEIGHTS = [35, 15, 5, 25, 5, 10, 10]


def build_rows(year: int, month: int, count: int, start_idx: int) -> list[dict[str, object]]:
    """Gera registos fictícios para o mês indicado com tipificações e observações variadas."""
    rows: list[dict[str, object]] = []

    for row_idx in range(count):
        start_at = random_datetime_in_month(year, month)
        duration_seconds = random.randint(75, 1600)
        end_at = start_at + timedelta(seconds=duration_seconds)

        outcome = random.choices(_OUTCOMES, weights=_OUTCOME_WEIGHTS, k=1)[0]
        call_id = f"C{year}{month:02d}-{start_idx + row_idx:06d}"

        tip = random.choice(TIPIFICATIONS)
        scenario = random.choices(_SCENARIOS, weights=_SCENARIO_WEIGHTS, k=1)[0]
        obs = _pick_observation(tip, scenario)

        rows.append(
            {
                "id_client": call_id,
                "name": random.choice(_ASSISTANT_NAMES),
                "startDate": start_at,
                "enddate": end_at,
                "service_type": random.choice(_SERVICE_TYPES),
                "category": tip['category'],
                "subcategory": tip['subcategory'],
                "third_category": tip['third_category'],
                "resolution": random.choice(_RETENTION_ACTIONS),
                "Ret Resolution": outcome,
                "observations": obs,
                "Day": start_at.date().isoformat(),
                "Week": f"{start_at.isocalendar().year}-W{start_at.isocalendar().week:02d}",
                "Month": start_at.strftime("%Y-%m"),
                "Exclude": "",
            }
        )

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera Excel ficticio para demos e testes internos")
    parser.add_argument("--per-month", type=int, default=500, help="Numero de registos por mes")
    parser.add_argument("--year", type=int, default=datetime.now().year, help="Ano para gerar dados")
    parser.add_argument("--seed", type=int, default=26042026, help="Seed para geracao deterministica")
    args = parser.parse_args()

    random.seed(args.seed)

    today = datetime.now().date()
    year = args.year

    all_rows: list[dict[str, object]] = []
    sequence = 1

    for month in range(1, today.month + 1):
        month_rows = build_rows(year=year, month=month, count=args.per_month, start_idx=sequence)
        sequence += len(month_rows)
        all_rows.extend(month_rows)

    df = pd.DataFrame(all_rows)

    output_dir = Path("sample_data")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"relatorio_ficticio_{year}_jan_ate_hoje_{args.per_month}_por_mes.xlsx"
    df.to_excel(output_path, index=False)

    print(f"Ficheiro criado: {output_path}")
    print(f"Total de registos: {len(df)}")

    # Resumo da distribuição para validação rápida
    cenarios = df['observations'].apply(
        lambda x: 'vazio' if x == '' else ('vago' if len(str(x)) < 30 else 'com obs')
    )
    print(f"\nDistribuição de observações:")
    print(cenarios.value_counts().to_string())
    print(f"\nTipificações distintas usadas: {df['third_category'].nunique()}")
    print(f"Assistentes: {sorted(df['name'].unique())}")


if __name__ == "__main__":
    main()
