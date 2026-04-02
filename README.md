# Internal Retention Analytics (Django)

Projeto Django local para analytics de retention, com foco inicial em inbound e importacao manual de Excel.

## Regras de negocio implementadas

- Cada linha do relatorio representa 1 chamada.
- Ret Resolution representa o resultado final oficial.
- resolution representa a acao detalhada de retencao.
- third_category representa o motivo de churn.
- service_type representa o tipo de atendimento.
- Duracao da chamada calculada como enddate - startDate.
- Call Drop tratado como outcome proprio.
- Inconsistencia de tipificacao monitorada quando resolution = Pendente e Ret Resolution = Retido.

## 1) Apps recomendados

- apps.core
- apps.imports_app
- apps.inbound
- apps.dashboards
- apps.quality

## 2) Responsabilidade de cada app

- apps.core: pagina inicial, navegacao e configuracoes de camada web.
- apps.imports_app: upload manual de Excel, lote de importacao e orquestracao do parsing.
- apps.inbound: modelo principal de chamadas inbound e metadados de atendimento.
- apps.dashboards: dashboards server-rendered por time e por agente.
- apps.quality: monitoramento de inconsistencias de tipificacao.

## 3) Estrutura de pastas

```text
dashboard/
	apps/
		core/
		imports_app/
			forms.py
			services.py
		inbound/
		dashboards/
		quality/
	config/
		settings.py
		urls.py
	templates/
		base.html
		core/home.html
		imports_app/upload.html
		dashboards/team_dashboard.html
		dashboards/agent_dashboard.html
	manage.py
	requirements.txt
	.gitignore
```

## 4) Ordem de implementacao para fase 1

1. Estrutura Django e apps base.
2. Modelo inbound com regras de negocio e duracao.
3. Importacao manual de Excel com validacao de colunas obrigatorias.
4. Deteccao de inconsistencias de tipificacao.
5. Dashboards por time e agente.
6. Refino de UX local e filtros adicionais.

## 5) MVP vs postergado

### MVP (fase 1)

- Importacao manual de Excel.
- Analise inbound.
- Dashboard por time.
- Dashboard por agente.
- Deteccao de inconsistencias de tipificacao.

### Postergar

- Fluxo outbound completo.
- Validacao avancada de tipificacao por regras configuraveis.
- Analise semantica de comentarios.
- API externa e arquitetura API-first.

## Como executar localmente

1. Criar ambiente virtual:

```powershell
python -m venv .venv
```

2. Instalar dependencias:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

3. Rodar migracoes:

```powershell
.\.venv\Scripts\python.exe manage.py makemigrations
.\.venv\Scripts\python.exe manage.py migrate
```

4. Iniciar servidor:

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Paginas principais:

- /
- /imports/
- /dashboards/teams/
- /dashboards/agents/
