from __future__ import annotations

import argparse
import calendar
import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


def random_datetime_in_month(year: int, month: int) -> datetime:
    last_day = calendar.monthrange(year, month)[1]
    day = random.randint(1, last_day)
    hour = random.randint(8, 19)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return datetime(year, month, day, hour, minute, second)


def build_rows(year: int, month: int, count: int, start_idx: int) -> list[dict[str, object]]:
    assistant_names = [
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
        "Karina Duarte",
        "Luis Tavares",
        "Marta Fernandes",
        "Nuno Lopes",
        "Olivia Ramos",
        "Paulo Correia",
        "Raquel Azevedo",
        "Sofia Moreira",
        "Tiago Freitas",
        "Vera Monteiro",
    ]

    service_types = [
        "Fibra",
        "Movel",
        "Voz pos-pago",
        "Voz pre-pago",
        "TV + Net",
    ]

    churn_reasons = [
        "Preco",
        "Concorrencia",
        "Qualidade",
        "Mudanca de morada",
        "Sem necessidade",
        "Cobertura",
    ]

    retention_actions = [
        "Desconto",
        "Upgrade",
        "Fidelizacao",
        "Oferta adicional",
        "Pendente",
        "Sem acao",
    ]

    outcomes = ["Retido", "Nao Retido", "Call Drop"]
    outcome_weights = [0.36, 0.58, 0.06]

    rows: list[dict[str, object]] = []
    for row_idx in range(count):
        start_at = random_datetime_in_month(year, month)
        duration_seconds = random.randint(75, 1600)
        end_at = start_at + timedelta(seconds=duration_seconds)

        outcome = random.choices(outcomes, weights=outcome_weights, k=1)[0]
        call_id = f"C{year}{month:02d}-{start_idx + row_idx:06d}"

        rows.append(
            {
                "id_client": call_id,
                "name": random.choice(assistant_names),
                "startDate": start_at,
                "enddate": end_at,
                "service_type": random.choice(service_types),
                "third_category": random.choice(churn_reasons),
                "resolution": random.choice(retention_actions),
                "Ret Resolution": outcome,
                "Day": start_at.date().isoformat(),
                "Week": f"{start_at.isocalendar().year}-W{start_at.isocalendar().week:02d}",
                "Month": start_at.strftime("%Y-%m"),
                "Exclude": "",
            }
        )

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera Excel ficticio para demos internas")
    parser.add_argument("--per-month", type=int, default=250, help="Numero de registos por mes")
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

    print(f"Arquivo criado: {output_path}")
    print(f"Total de registos: {len(df)}")


if __name__ == "__main__":
    main()
