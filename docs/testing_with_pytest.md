# Testes com Pytest e Coverage

## Instalacao

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

Relatorio no terminal por ficheiro:

```powershell
& "c:/Users/tutas/Documents/Projetos GitHUB/dashboard/.venv/Scripts/python.exe" -m pytest --cov --cov-config=.coveragerc --cov-report=term-missing
```

Relatorio HTML:

```powershell
& "c:/Users/tutas/Documents/Projetos GitHUB/dashboard/.venv/Scripts/python.exe" -m pytest --cov --cov-config=.coveragerc --cov-report=html
```

Meta minima configurada: `fail_under = 85` em `.coveragerc`.

## Estrategia pratica para chegar aos 85%

### Fase 1 (maior retorno)
- `imports_app/services.py`: pipeline, resumo, deduplicacao
- `dashboards/services.py`: KPIs e metricas principais

### Fase 2
- `dashboards/selectors.py`: filtros de data e assistente, agregacoes
- `inbound/models.py`: regras de `save` e `clean`

### Fase 3
- views principais para garantir status/rotas/contexto
- evitar testar detalhes de template

### Fase 4
- edge cases de validacao e erros de importacao
- cenarios com listas vazias, datas invalidas e sem resultados

## Onde vale investir tempo
- logica de negocio em services/selectors
- regressao de resumo operacional dos lotes
- regras de deduplicacao

## Onde evitar overtesting
- HTML/CSS
- asserts de implementacao interna
- mocks excessivos quando DB de teste resolve
