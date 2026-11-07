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
