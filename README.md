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
- `resolution` representa a resolucao operacional detalhada da chamada.
- `third_category` representa o motivo de churn.
- `service_type` representa o tipo de atendimento.
- A duracao da chamada e calculada a partir da diferenca entre inicio e fim.
- `Call Drop` e tratado como outcome proprio.
- Inconsistencias de tipificacao sao monitorizadas quando a combinacao de campos viola as regras de qualidade definidas.

### Priorizacao de auditoria (aba Dia anterior)

Na aba `Dia anterior`, a lista de chamadas para auditoria e priorizada por um score explicavel chamado `audit_priority_score` (intervalo de 0 a 100).

Formula aplicada (soma de pesos):

- Cliente nao retido: `+25`
- Sem resolucao registada: `+30`
- Tipificacao (third_category) com potencial de retencao: `+20`
- Assistente abaixo da media do dia: `+15`
- Inconsistencia de tipificacao: `+10`
- Alta taxa de nao retencao no servico/tipificacao: `+10`

Regras de interpretacao:

- Score final e truncado para maximo de `100`.
- Cada chamada exposta para auditoria inclui `audit_reasons` com os motivos que contribuiram para o score.
- A lista e ordenada por `audit_priority_score DESC`.
- O dashboard mostra apenas o `top 15` de chamadas mais criticas.
- Base de analise: apenas chamadas com resultado `Nao Retido` entram no ranking de auditoria.

Definicoes operacionais (importante):

- `Sem resolucao` = valor da dimensao `retention_action` (resolucao operacional), nao e uma tipificacao de motivo.
- `Nao tipificado` = ausencia/erro de tipificacao de motivo (`third_category` / `churn_reason`), conceito diferente de `Sem resolucao`.
- Uma chamada pode estar `Sem resolucao` e ainda assim estar tipificada; tambem pode estar tipificada e nao estar `Sem resolucao`.

Leitura operacional sugerida:

- `>= 60`: critico (intervencao imediata)
- `40-59`: alto (revisao prioritaria)
- `< 40`: medio (monitorizacao)

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

### Configuracao de performance: Analise de Tipificacoes

Para melhorar tempo de carregamento da pagina `Analise de Tipificacoes`, o sistema aplica dois comportamentos:

- Por defeito, quando nao e informado intervalo de datas, a pagina carrega apenas o dia anterior.
- A tabela usa um limite maximo de registos configuravel por ambiente.

Variavel:

```env
DASHBOARD_TYPING_TABLE_LIMIT=500
```

Notas:

- `500` = carrega no maximo 500 interacoes na tabela.
- `0` (ou valor negativo) = sem limite de registos.
- Para periodos longos e muito volume, manter limite ajuda a pagina a abrir mais rapido.

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

## Producao (static files e seguranca basica)

- `WhiteNoise` serve os static files em producao sem dependencia externa.
- `DEBUG`, `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` sao lidos por variaveis de ambiente.
- Com `DEBUG=False`, o storage de static usa arquivos comprimidos e com hash (`CompressedManifestStaticFilesStorage`).

### Comandos essenciais para preparar deploy

```powershell
& ".\.venv\Scripts\python.exe" manage.py migrate
& ".\.venv\Scripts\python.exe" manage.py collectstatic --noinput
```

## Deploy no Render

O repositório inclui o ficheiro `render.yaml` para criar o Web Service automaticamente.

### O que esta configurado

- `buildCommand`: instala dependencias, executa `migrate` e depois `collectstatic`.
- `startCommand`: sobe a app com `gunicorn` usando `config.wsgi:application`.
- Variaveis de ambiente de producao:
	- `DEBUG=False`
	- `SECRET_KEY` gerado no Render
	- `ALLOWED_HOSTS`
	- `CSRF_TRUSTED_ORIGINS`
	- `DATABASE_URL` (definido manualmente com a URL do Supabase)

### Passos no Render

1. Criar novo serviço via Blueprint apontando para este repositório.
2. Confirmar o nome/domínio final e ajustar `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` no painel.
3. Definir `DATABASE_URL` com a string do Supabase.
4. Fazer deploy.

### Nota sobre `DATABASE_URL` (Supabase)

- Use a connection string completa com `sslmode=require`.
- Se a password tiver caracteres especiais (`@`, `:`, `/`, `#`, `%`, `?`), aplique URL encoding.

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
- `/dashboards/previous-day/`

Nota: para utilizadores do grupo `Assistentes`, o fluxo normal de navegacao privilegia a pagina individual do proprio assistente em vez das paginas globais.

### Exports CSV

- `/dashboards/services/export.csv`
- `/dashboards/assistants/export.csv`
- `/dashboards/inconsistencies/export.csv`

### Exports Excel

- `/dashboards/previous-day/export.xlsx`
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
