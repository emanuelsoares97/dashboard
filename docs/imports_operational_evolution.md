# Evolucao Incremental de Importacoes

## Fase 1: Operacao e Rastreabilidade

Objetivo: dar visibilidade operacional sem reescrever pipeline.

Entregas:
- historico paginado de lotes
- detalhe operacional por lote
- contadores claros de importacao
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

Objetivo: proteger pipeline contra regressao.

Cobertura:
- parsing/mapping: estabilidade de hash
- deduplicacao: intra-ficheiro e inter-import
- persistencia: criacao de interactions e estados das raw rows
- resumo final: contadores e status do lote
- views: upload, historico e detalhe

### Exemplos Django ja implementados

- `apps/imports_app/tests/test_import_service.py`
- `apps/imports_app/tests/test_import_views.py`
- `apps/imports_app/tests/test_row_mapper.py`

### Exemplo rapido em pytest (opcional)

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

## Proximos passos recomendados

1. Adicionar filtro por status e periodo no historico.
2. Exportar detalhe do lote para CSV.
3. Adicionar `pytest` com marcadores por camada (parser, service, view).
4. Instrumentar tempos de importacao por lote para observabilidade.
