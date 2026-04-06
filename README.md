# Internal Retention Analytics

Projeto Django para importacao, normalizacao e analise operacional de chamadas inbound, com dashboards server-rendered, exports CSV e monitorizacao de inconsistencias de tipificacao.

## Visao geral

O sistema foi desenhado para apoiar analise de retenções a partir de ficheiros Excel importados manualmente. O fluxo principal hoje e:

1. importar um ficheiro Excel;
2. validar e persistir os registos de inbound;
3. sinalizar inconsistencias de qualidade;
4. consultar dashboards analiticos por varias dimensoes;
5. exportar tabelas operacionais em CSV.

## Regras de negocio atualmente implementadas

- Cada linha importada representa 1 chamada.
- `Ret Resolution` representa o resultado final oficial.
- `resolution` representa a acao detalhada de retencao.
- `third_category` representa o motivo de churn.
- `service_type` representa o tipo de atendimento.
- A duracao da chamada e calculada a partir da diferenca entre inicio e fim.
- `Call Drop` e tratado como outcome proprio.
- Inconsistencias de tipificacao sao monitorizadas quando a combinacao de campos viola as regras de qualidade definidas.

## Controlo de acesso

O projeto usa autenticacao Django com controlo de acesso por grupos.

### Grupos suportados

- `Assistentes`
- `Supervisores`
- `Coordenacao`
- `Coordenação`

Os grupos `Coordenacao` e `Coordenação` sao tratados como equivalentes para compatibilidade com dados ja existentes.

### Regras por perfil

- `superuser`: acesso total ao sistema, sem restricoes de assistente.
- `Supervisores`: acesso completo aos dashboards, analise sensivel, exports e importacoes.
- `Coordenacao` / `Coordenação`: acesso completo aos dashboards, analise sensivel, exports e importacoes.
- `Assistentes`: acesso apenas aos seus proprios dados no dashboard.

### Ligacao entre utilizador e assistente

Existe uma ligacao explicita entre utilizadores autenticados e registos de assistente atraves de `Agent.user`.

Esta associacao permite:

- redirecionar automaticamente o assistente para a sua pagina individual apos login;
- limitar a visualizacao do assistente aos seus proprios dados;
- gerir a associacao tanto no admin de `Agent` como no admin de `User`.

### Comportamento das views por perfil

- Assistentes autenticados sao encaminhados para a sua pagina individual de assistente quando aplicavel.
- Assistentes nao veem opcoes de importacao na navegacao.
- Rotas de importacao continuam protegidas no backend e devolvem negacao de acesso para perfis sem permissao.
- Paginas sensiveis do dashboard continuam protegidas por permissao dedicada, mesmo que o utilizador tente aceder diretamente por URL.
- Supervisao, coordenacao e superuser mantem acesso integral a navegacao e vistas analiticas.

## Apps principais

- `apps.core`: homepage e navegação base.
- `apps.imports_app`: upload de Excel, historico de importacoes e detalhe de lotes.
- `apps.inbound`: modelos e dados centrais de chamadas inbound.
- `apps.dashboards`: selectors, services e views dos dashboards analiticos.
- `apps.quality`: flags e controlo de qualidade dos dados importados.

## Arquitetura atual

O projeto ja nao depende de ficheiros monoliticos nas camadas principais do dashboard.

### `apps.dashboards.services`

- `tables.py`: KPIs, tabelas e agregados prontos para frontend.
- `comparison.py`: comparacao com periodo anterior e deltas.
- `insights.py`: insights automaticos.
- `payload.py`: orquestracao do payload principal do dashboard.
- `__init__.py`: fachada compatível para imports antigos.

### `apps.dashboards.views`

- `helpers.py`: filtros, querystring e contexto comum.
- `pages.py`: paginas principais do dashboard.
- `exports.py`: exports CSV.
- `legacy.py`: redirects de rotas antigas.
- `__init__.py`: fachada compatível para imports antigos.

### `apps.dashboards.selectors`

- `base.py`: queryset base, filtros comuns e opcoes globais.
- `aggregates.py`: KPIs e agregacoes por dominio.
- `temporal.py`: agregacoes temporais.
- `assistants.py`: breakdowns e ranking por assistente.
- `quality.py`: queries de inconsistencias.
- `__init__.py`: fachada compatível para o namespace `apps.dashboards.selectors`.

## Estrutura resumida

```text
dashboard/
	apps/
		core/
		dashboards/
			selectors/
			services/
			views/
			tests/
		imports_app/
			parsers/
			persistence/
			rules/
			tests/
			validators/
		inbound/
		quality/
	config/
	docs/
	sample_data/
	static/
	templates/
	manage.py
	requirements.txt
	pytest.ini
```

## Como executar localmente

### 1. Criar ambiente virtual

```powershell
python -m venv .venv
```

### 2. Instalar dependencias da aplicacao

```powershell
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
```

### 3. Aplicar migracoes

```powershell
& ".\.venv\Scripts\python.exe" manage.py migrate
```

### 4. Iniciar o servidor

```powershell
& ".\.venv\Scripts\python.exe" manage.py runserver
```

## Base de dados (PostgreSQL / Supabase)

O projeto usa `DATABASE_URL` como configuracao principal de base de dados.

- Se `DATABASE_URL` estiver definido, o Django usa PostgreSQL (incluindo Supabase).
- Se `DATABASE_URL` nao estiver definido, o projeto usa SQLite local como fallback de desenvolvimento.

### 1. Criar ficheiro `.env`

```powershell
Copy-Item .env.example .env
```

### 2. Definir a connection string

Exemplo:

```env
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require
```

### 3. Aplicar migracoes na base PostgreSQL

```powershell
& ".\.venv\Scripts\python.exe" manage.py migrate
```

### Nota sobre Supabase: direct connection vs pooler (Supavisor)

- `Pooler/Supavisor` e recomendado para aplicacoes web e workers (melhor controlo de conexoes).
- `Direct connection` pode ser usada em operacoes administrativas pontuais.
- Em ambos os casos, mantenha `sslmode=require` na URL.

## Rotas principais

### Core

- `/`

### Importacoes

- `/imports/`
- `/imports/history/`
- `/imports/history/<batch_id>/`

### Dashboards

- `/dashboards/overview/`
- `/dashboards/churn-reasons/`
- `/dashboards/retention-actions/`
- `/dashboards/services/`
- `/dashboards/assistants/`
- `/dashboards/assistants/<assistant_id>/`
- `/dashboards/inconsistencies/`
- `/dashboards/insights/`
- `/dashboards/monthly-rates/`
- `/dashboards/daily-rates/`

Nota: para utilizadores do grupo `Assistentes`, o fluxo normal de navegacao privilegia a pagina individual do proprio assistente em vez das paginas globais.

### Exports CSV

- `/dashboards/services/export.csv`
- `/dashboards/assistants/export.csv`
- `/dashboards/inconsistencies/export.csv`
- `/dashboards/monthly-rates/export.csv`
- `/dashboards/daily-rates/export.csv`

### Rotas legadas mantidas por compatibilidade

- `/dashboards/teams/`
- `/dashboards/agents/`

## Testes

### Correr a suite completa

```powershell
& ".\.venv\Scripts\python.exe" -m pytest
```

### Correr testes com coverage no terminal

```powershell
& ".\.venv\Scripts\python.exe" -m pytest --cov --cov-config=.coveragerc --cov-report=term-missing
```

### Gerar coverage HTML

```powershell
& ".\.venv\Scripts\python.exe" -m pytest --cov --cov-config=.coveragerc --cov-report=html
```

Documentacao complementar de testes: `docs/testing_with_pytest.md`

## Dados e ficheiros uteis

- `sample_data/`: ficheiros de apoio para testes manuais.
- `media/imports/`: ficheiros importados em ambiente local.
- `test_media/imports/`: suporte a testes automatizados.
- `docs/imports_operational_evolution.md`: notas de evolucao funcional do fluxo de importacao.
- `docs/public_contracts.md`: contratos publicos estaveis das fachadas modulares.

## Stack principal

- Django 6.0.3
- Pytest 8.3.5
- pytest-django 4.11.1
- pytest-cov 6.1.1
- pandas / openpyxl para leitura e tratamento de Excel

## Estado atual

- Projeto funcional em ambiente local.
- Camadas de `services`, `views` e `selectors` do dashboard ja modularizadas.
- Imports antigos preservados com fachadas compatíveis.
- Controlo de acesso por grupos aplicado nas views e navegacao.
- Fluxo especifico para assistentes implementado com restricao a dados proprios.
- Suite automatizada verde.
