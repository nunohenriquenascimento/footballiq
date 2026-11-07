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
