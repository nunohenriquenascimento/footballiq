# Arquitetura inicial

## Âmbito

Preparar um pacote Python instalável e um fluxo mínimo de desenvolvimento.
Não existem funcionalidades de negócio, acesso a dados, APIs ou infraestrutura.

## Decisões

- **Python 3.14:** versão mínima alinhada com o interpretador disponível na
  criação do projeto. Outras versões não foram validadas nesta etapa.
- **Src-layout:** o código distribuível vive em `src/footballiq/`. Importar o
  pacote requer instalação, reduzindo diferenças entre desenvolvimento e uso.
- **Setuptools:** backend de construção com descoberta explícita em `src/`.
  O `pyproject.toml` concentra metadados e configuração.
- **Sem dependências de execução:** nenhuma biblioteca de dados ou framework é
  necessária antes de existir um requisito concreto.
- **Pytest e Ruff:** dependências opcionais de desenvolvimento para testes,
  lint, ordenação de imports e formatação. As faixas de versões permitem
  atualizações; ainda não existe lockfile, pelo que não garantem ambientes
  idênticos entre instalações futuras.
- **Teste inicial (FI-002):** `tests/test_package.py` verifica a importação do
  pacote instalado. O modo de importação `importlib` permite fazê-lo sem
  manipular caminhos de importação. Testes de negócio serão adicionados com
  as funcionalidades correspondentes.
- **Configuração futura:** `.env.example` não contém variáveis fictícias nem
  implica a instalação de um carregador de ficheiros `.env`.

## Convenções

Adicionar docstrings a funções e classes relevantes quando forem introduzidas.
Usar comentários para explicar decisões não óbvias, sem repetir o código.
Manter o import do pacote livre de efeitos laterais.

## Evolução

O próximo incremento deve definir um pequeno caso de uso, os seus critérios de
aceitação e os testes correspondentes. Escolhas de armazenamento, APIs e
infraestrutura exigem uma nova instrução e ficam fora desta fundação.

## Pipeline ETL inicial (FI-004)

A segunda etapa do projeto introduz um pipeline ETL mínimo para registrar
resultados de partidas de futebol em formato JSON.

### Objetivo

O objetivo pedagógico é mostrar, em código simples, a separação entre:

- Extracção: leitura de dados de origem.
- Validação: confirmação de estrutura e integridade.
- Transformação: cálculo de métricas derivadas.
- Carga: escrita do ficheiro JSON de resultados.

### Decisões

- **Dados fictícios em JSON:** a fonte de dados é um ficheiro local em
  `data/sample/matches.json`. Evita dependências externas e mantém o processo
  simples de aprender.
- **Biblioteca padrão:** a implementação usa apenas `json`, `pathlib` e
  `argparse`, sem instalar frameworks ou bases de dados.
- **Separação por fases:** cada etapa reconhece uma responsabilidade concreta,
  o que melhora testabilidade e facilita a manutenção.
- **Diretório de resultados:** `results/` fica ignorado no Git para separar o
  output executado dos ficheiros de código e documentação.

### Execução

O fluxo principal vive em `src/footballiq/etl.py` e pode ser invocado pelo
pacote com:

```sh
.venv/bin/python -m footballiq --input data/sample/matches.json --output results/matches_summary.json
```

A CLI aceita argumentos opcionais para `--input` e `--output`, permitindo testar
ambientes diferentes sem alterar o código.

### Limites desta fase

Este ETL não persiste em base de dados nem publica APIs. O foco está em criar uma
base didática de processamento data-centric com validação e testes unitários
claros.
