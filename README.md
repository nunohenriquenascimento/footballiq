# FootballIQ

Projeto de portefólio dedicado a Data Science, Data Engineering, Machine Learning
e AI Engineering no contexto do futebol.

Esta primeira etapa contém apenas a fundação Python: não inclui funcionalidades
de negócio, base de dados, API ou infraestrutura.

## Ambiente de desenvolvimento

Requer Python 3.14 ou superior. A versão inicial foi validada com Python 3.14.

Criar um ambiente virtual para isolar as ferramentas do projeto:

```sh
python3 -m venv .venv
```

Instalar o pacote em modo editável e as ferramentas de desenvolvimento; assim,
as alterações em `src/` ficam disponíveis sem reinstalar o pacote:

```sh
.venv/bin/python -m pip install -e '.[dev]'
```

Executar os testes e verificar lint e formatação, sem alterar ficheiros:

```sh
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
```

A suite inicial verifica que o pacote instalado pode ser importado pelo nome
`footballiq`. Ainda não existem testes de negócio, pois não há funcionalidades
de negócio implementadas.

## Ligação local ao PostgreSQL

A camada de leitura do projeto usa `psycopg` 3 para consultar a base de dados
local do FootballIQ sem qualquer escrita, atualização ou eliminação.

Adicionar a dependência do pacote no ambiente virtual:

```sh
.venv/bin/python -m pip install -e '.[dev]'
```

Definir as variáveis de ambiente necessárias (sem guardar segredos no código):

```sh
export FOOTBALLIQ_DB_HOST=127.0.0.1
export FOOTBALLIQ_DB_PORT=5432
export FOOTBALLIQ_DB_NAME=footballiq_dev
export FOOTBALLIQ_DB_USER=footballiq
export FOOTBALLIQ_DB_PASSWORD=""
export FOOTBALLIQ_DB_SSLMODE=prefer
```

O projeto não assume uma role fixa. O utilizador é obrigatório e deve ser
fornecido por `FOOTBALLIQ_DB_USER`; o valor concreto depende do cluster local.
Na máquina validada, a role correta para a base `footballiq_dev` foi `footballiq`.

O ficheiro [.env.example](.env.example) contém o mesmo exemplo sem segredos.
A base `footballiq_dev` deve existir e ser a única alvo da integração. Quando a
configuração fica incompleta, a aplicação não tenta ligar a outra base por
inferência.

### Teste de integração opcional

Os testes de integração são explícitos e desativados por defeito. Só devem
executar-se quando o ambiente de desenvolvimento estiver corretamente configurado
para `footballiq_dev`:

```sh
export FOOTBALLIQ_DB_RUN_INTEGRATION=1
export FOOTBALLIQ_DB_NAME=footballiq_dev
export FOOTBALLIQ_DB_USER=footballiq
.venv/bin/python -m pytest tests/test_db_integration.py -v
```

O teste valida apenas a ligação ao PostgreSQL e confirma que a base ativa é
`footballiq_dev`. Não realiza inserções, alterações ou exclusões.

### Testes unitários versus integração

- Testes unitários: validam configuração e lógica de leitura sem depender do
  servidor PostgreSQL; executam-se por defeito.
- Testes de integração: exigem a variável `FOOTBALLIQ_DB_RUN_INTEGRATION=1` e
  o alvo `footballiq_dev`; são reservados para validação local do ambiente.

## Persistência idempotente para PostgreSQL

A função `persist_matches` vive em `src/footballiq/db/persistence.py` e aceita uma
sequência de partidas já validadas pelo ETL. Ela usa a chave de negócio
`(source, source_match_id)` e executa `INSERT ... ON CONFLICT DO UPDATE` para
manter a carga idempotente.

```python
from footballiq.db.persistence import persist_matches

with connect() as connection:
    try:
        connection.execute("BEGIN;")
        count = persist_matches(matches, source="sample", connection=connection)
        connection.rollback()
    except Exception:
        connection.rollback()
        raise
```

A regra de transação fica controlada pelo chamador. A função não decide por si
`COMMIT` ou `ROLLBACK`; se receber uma conexão, respeita a transação existente e
somente grava os dados no contexto da operação atual. Se não receber uma
conexão, cria a sua própria ligação, mas continua a depender do bloco `with` do
objeto `psycopg` para fechar a sessão.

A resolução de equipas para `source='sample'` é provisória e baseada no nome da
equipa em contexto de carga. O projeto não assume `UNIQUE` global em
`teams.name` e levanta erro explícito quando o mesmo nome aparece em múltiplas
linhas da tabela, em vez de escolher arbitrariamente uma linha.

A persistência é também mais segura do que uma carga ad hoc porque usa parâmetros
SQL em todos os inserts e não altera jogos de outras fontes. A lógica restringe
os updates ao mesmo `source` e `source_match_id`, preservando a integridade do
resto dos dados.

## Integração contínua (CI)

Este projeto usa GitHub Actions para validar automaticamente o código em cada
Pull Request e em cada push para a branch `main`.

O workflow em [`.github/workflows/ci.yml`](.github/workflows/ci.yml) executa os
mesmos comandos verificados localmente:

```sh
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

A configuração é deliberately simples: apenas instala o pacote em modo editável
com as dependências de desenvolvimento, usa o runner oficial do GitHub Actions e
não introduz serviços externos, deploy ou containers nesta etapa.

## Estrutura

- `README.md`: objetivo, preparação do ambiente e comandos de verificação.
- `AGENTS.md`: instruções permanentes para alterações e colaboração técnica.
- `.gitignore`: exclui ambientes locais, segredos, caches e artefactos gerados.
- `.env.example`: documenta futuras variáveis de ambiente, sem guardar segredos.
- `pyproject.toml`: metadados, empacotamento e configuração das ferramentas.
- `src/footballiq/__init__.py`: identifica o pacote Python, sem efeitos laterais.
- `tests/test_package.py`: primeiro teste de importação do pacote instalado.
- `docs/architecture.md`: decisões técnicas e limites desta etapa.

Consultar [as decisões de arquitetura](docs/architecture.md) antes de expandir
o projeto.

## Pipeline ETL inicial

A segunda etapa introduz um pipeline ETL simples para dados fictícios de jogos
criados em `data/sample/matches.json`.

### Fluxo

1. `Extract`: lê o JSON com as partidas e valida o conteúdo.
2. `Transform`: calcula métricas por jogo: total de golos, diferença de golos e
   vencedor (`home`, `away` ou `draw`).
3. `Load`: grava um ficheiro em `results/matches_summary.json`, que fica ignorado
   pelo Git para não misturar artefactos de execução com o código do projeto.

### Executar

Instalar o pacote em modo editável no ambiente de desenvolvimento:

```sh
.venv/bin/python -m pip install -e '.[dev]'
```

Executar o pipeline com os dados de exemplo:

```sh
.venv/bin/python -m footballiq --input data/sample/matches.json --output results/matches_summary.json
```

O módulo `footballiq.etl` expõe funções separadas para extração, validação,
transformação, carregamento e execução do pipeline. A estrutura foi desenhada para
ser fácil de testar sem depender de bibliotecas externas.
