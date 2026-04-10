# Evolução Incremental de Importações

## Fase 1: Operação e Rastreabilidade

Objetivo: dar visibilidade operacional sem reescrever pipeline.

Entregas:
- histórico paginado de lotes
- detalhe operacional por lote
- contadores claros de importação
- amostras de duplicadas e invalidas

## Fase 2: Clareza de Duplicados

Objetivo: distinguir origem de duplicados com baixo acoplamento.

Entregas:
- `duplicate_rows`
- `duplicate_in_file_rows`
- `duplicate_previous_rows`
- `processing_status` por linha crua
- `processing_error` por linha crua

## Fase 3: Testes Automatizados

Objetivo: proteger pipeline contra regressão.

Cobertura:
- parsing/mapping: estabilidade de hash
- deduplicação: intra-ficheiro e inter-import
- persistência: criação de interactions e estados das raw rows
- resumo final: contadores e status do lote
- views: upload, historico e detalhe

### Exemplos Django já implementados

- `apps/imports_app/tests/test_import_service.py`
- `apps/imports_app/tests/test_import_views.py`
- `apps/imports_app/tests/test_row_mapper.py`

### Exemplo rápido em pytest (opcional)

```python
import pandas as pd
from pathlib import Path

from apps.imports_app.models import ImportBatch
from apps.imports_app.services import import_excel


def test_import_ignores_duplicate_previous(mocker, db):
	dataframe = pd.DataFrame([
		{
			'external_call_id': 'c1',
			'agent_name': 'Ana',
			'start_date': '2026-01-01T10:00:00Z',
			'end_date': '2026-01-01T10:10:00Z',
			'final_outcome': 'Retido',
			'retention_action': 'Oferta',
		}
	])
	mocker.patch('apps.imports_app.services.read_excel_dataframe', return_value=dataframe)

	first = ImportBatch.objects.create(original_filename='a.xlsx')
	second = ImportBatch.objects.create(original_filename='b.xlsx')

	import_excel(Path('a.xlsx'), first)
	summary = import_excel(Path('b.xlsx'), second)

	assert summary['duplicate_previous_rows'] == 1
```

## Próximos passos recomendados

1. Adicionar filtro por status e período no histórico.
2. Exportar detalhe do lote para CSV.
3. Adicionar `pytest` com marcadores por camada (parser, service, view).
4. Instrumentar tempos de importação por lote para observabilidade.

## Nota de terminologia

- Nos contratos internos de importação e persistência, o campo técnico continua `retention_action` por compatibilidade.
- Na UI e na documentação operacional, usar preferencialmente o termo `resolução`.
