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
