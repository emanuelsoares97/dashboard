# Contratos Publicos Estaveis

Este documento resume os pontos de entrada considerados estaveis para uso interno no projeto. O objetivo e permitir refatoracoes estruturais sem quebrar imports existentes entre apps e camadas.

## Regra geral

- Preferir importar pelas fachadas `__init__.py` quando elas existirem.
- Evitar depender de helpers privados de modulos internos novos, exceto quando isso ja fizer parte do contrato atual do projeto.
- Ao modularizar uma camada, preservar o caminho de import antigo enquanto houver codigo ou testes que dependam dele.

## Dashboard

### `apps.dashboards.services`

Contrato estavel atual:

- `build_dashboard_payload`
- `build_frontend_payload`
- `build_assistant_detail`
- `build_churn_reason_table`
- `build_retention_action_table`
- `build_service_type_table`
- `build_temporal_table`
- `build_monthly_rates_table`
- `build_daily_rates_table`
- `build_monthly_rates_summary`
- `build_daily_rates_summary`
- `build_assistant_ranking_table`
- `build_inconsistency_section`
- `build_tipification_tables`
- `calculate_general_kpis`
- `generate_insights`
- `_compute_delta`

Nota:

- Existem outros re-exports privados por compatibilidade. Devem ser tratados como legado interno e nao como primeira escolha para novo codigo.

### `apps.dashboards.views`

Contrato estavel atual para URLs e imports existentes:

- `overview`
- `churn_reasons`
- `retention_actions`
- `services`
- `assistants`
- `assistant_detail`
- `inconsistencies`
- `insights`
- `monthly_rates`
- `daily_rates`
- `services_csv`
- `assistants_csv`
- `inconsistencies_csv`
- `monthly_rates_csv`
- `daily_rates_csv`
- `team_dashboard`
- `agent_dashboard`

### `apps.dashboards.selectors`

Contrato estavel atual como namespace unico:

- `get_inbound_queryset`
- `apply_filters`
- `select_global_filter_options`
- `get_single_assistant_id`
- `select_kpis_base`
- `select_by_churn_reason`
- `select_top_churn_reason_by_volume`
- `select_by_retention_action`
- `select_top_retention_action_by_volume`
- `select_by_service_type`
- `select_temporal`
- `select_assistant_ranking_base`
- `select_assistant_churn_breakdown`
- `select_assistant_action_breakdown`
- `select_inconsistency_count_by_agent`
- `select_inconsistency_by_assistant`
- `select_inconsistency_table`
- `select_tipification_breakdown`

## Imports App

### `apps.imports_app.services`

Contrato estavel atual:

- `import_excel`
- `list_import_batches`
- `get_import_batch_detail`
- `build_batch_detail_context`

Compatibilidade adicional preservada:

- O caminho `apps.imports_app.services.read_excel_dataframe` continua patchable em testes.

### `apps.imports_app.views`

Contrato estavel atual:

- `upload_excel`
- `import_history`
- `import_batch_detail`

Compatibilidade adicional preservada:

- O caminho `apps.imports_app.views.import_excel` continua patchable em testes.

## Boas praticas para proximas refatoracoes

- Antes de mover funcoes, verificar quem importa a fachada publica e quem faz patch por caminho absoluto.
- Quando houver testes a fazer patch de um simbolo, preservar esse caminho durante a transicao.
- Se um helper privado for re-exportado apenas por compatibilidade, considerar adicionar teste de contrato antes de novas mudancas.
- Se um contrato deixar de ser necessario, remover apenas num bloco explicito e com atualizacao de testes/documentacao.