# Testes com Pytest e Coverage

## Instalação

```powershell
& "c:/Users/tutas/Documents/Projetos GitHUB/dashboard/.venv/Scripts/python.exe" -m pip install -r requirements-dev.txt
```

## Estrutura recomendada

```text
apps/
  imports_app/
    tests/
      test_services.py
      test_deduplication.py
      test_pipeline.py
  dashboards/
    tests/
      test_services.py
      test_selectors.py
      test_views.py
  inbound/
    tests/
      test_models.py
```

## Como correr testes

```powershell
& "c:/Users/tutas/Documents/Projetos GitHUB/dashboard/.venv/Scripts/python.exe" -m pytest
```

## Como medir coverage

Relatório no terminal por ficheiro:

```powershell
& "c:/Users/tutas/Documents/Projetos GitHUB/dashboard/.venv/Scripts/python.exe" -m pytest --cov --cov-config=.coveragerc --cov-report=term-missing
```

Relatório HTML:

```powershell
& "c:/Users/tutas/Documents/Projetos GitHUB/dashboard/.venv/Scripts/python.exe" -m pytest --cov --cov-config=.coveragerc --cov-report=html
```

Meta minima configurada: `fail_under = 85` em `.coveragerc`.

## Estratégia prática para chegar aos 85%

### Fase 1 (maior retorno)
- `imports_app/services.py`: pipeline, resumo, deduplicação
- `dashboards/services.py`: KPIs e métricas principais

### Fase 2
- `dashboards/selectors.py`: filtros de data e assistente, agregações
- `inbound/models.py`: regras de `save` e `clean`

### Fase 3
- views principais para garantir status/rotas/contexto
- evitar testar detalhes de template

### Fase 4
- edge cases de validação e erros de importação
- cenários com listas vazias, datas inválidas e sem resultados

## Onde vale investir tempo
- lógica de negócio em services/selectors
- regressão de resumo operacional dos lotes
- regras de deduplicação

## Onde evitar overtesting
- HTML/CSS
- asserts de implementação interna
- mocks excessivos quando DB de teste resolve
