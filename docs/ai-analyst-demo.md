# FI-008.1 — Demonstração factual do FootballIQ AI Analyst

Protótipo local de terminal para responder a **«Analisa os últimos cinco jogos
da minha equipa.»** Apenas dados fictícios; por defeito sem LLM, PostgreSQL ou rede.
FI-008.2 acrescenta [seleção opcional com Ollama](ollama-analyst.md), preservando
integralmente o factual descrito nesta página.

## Executar

Num checkout completo, com o pacote já instalado em modo editável:

```powershell
.\.venv\Scripts\python.exe -m footballiq.analyst_demo
.\.venv\Scripts\python.exe -m footballiq.analyst_demo --fixture partial_match
.\.venv\Scripts\python.exe -m footballiq.analyst_demo --fixture empty
```

Em Linux/macOS, substituir o executável por `.venv/bin/python`.
O primeiro comando equivale a `--fixture complete_five`. `--help` apresenta as
opções. Não é preciso configurar `.env`, base de dados, modelo ou credenciais.
O comando escreve apenas no terminal. `python -m footballiq` mantém a CLI ETL
existente; a demonstração usa um módulo separado para preservar essa interface.

## O que observar

A resposta começa por **«Dados fictícios — demonstração»** e mostra:

- Cinco jogos, datas UTC e casa/fora, ordenados pelo motor. Os jogos 10 e 9 têm
  a mesma data e mantêm o desempate numérico (10 antes de 9).
- Resultados na perspetiva da equipa: 2–1, 1–0, 1–1, 0–2 e 0–0.
- Duas vitórias, dois empates, uma derrota; quatro golos marcados e quatro
  sofridos. Médias de 0,8 golos marcados e sofridos por jogo verificado.
- Remates, cartões, substituições e distribuição temporal apenas segundo os
  valores e a cobertura fornecidos pelo Analytics Engine.
- Cobertura n/N para cada categoria, com N igual ao número de jogos encontrados,
  e motivos por jogo quando uma categoria está indisponível.
- Origem, snapshot, versões por jogo, IDs de eventos e proveniência do resultado.

Pontos ficam indisponíveis: não se fornece política de pontos nem se presume um
regulamento oficial. Não se calculam xG, posse ou explicações táticas especulativas.

No cenário `partial_match`, há apenas um jogo, sem resultado verificado:
as métricas continuam indisponíveis, sem converter `null` em zero. No cenário
`empty`, não há jogos, totais ou médias; cobertura 0/0 não significa zero golos.
Se uma janela estiver parcialmente coberta, o apresentador distingue o subtotal
conhecido do total indisponível da janela.

## Origem e decisões

`src/footballiq/analyst_demo.py` carrega exclusivamente os três JSON existentes em
`tests/fixtures/integration/`. Não aceita paths, uploads, JSON arbitrário ou dados
do Tracker. A lista fechada evita selecionar acidentalmente ficheiros reais.
Um SHA-256 de cada texto aprovado, normalizado para LF, deteta substituições
acidentais antes de apresentar conteúdo. Não é autenticação de produção:
alterar intencionalmente o código e o hash pode contornar essa guarda.

As fixtures são propriedade dos testes e continuam a ter uma única origem,
sem cópias divergentes no pacote. Consequência explícita: este protótipo requer
o checkout; uma wheel isolada, sem `tests/`, falha com mensagem clara.
Se uma fixture for revista intencionalmente, rever conteúdo e hash em conjunto.

Não foram acrescentadas dependências nem fórmulas. `load_demo_report` chama
`analyze_recent_matches`; o apresentador só traduz rótulos e formata valores.
Nenhum modelo existente, contrato JSON, ETL ou persistência foi alterado.

Escolheu-se terminal porque não existe frontend neste repositório. Streamlit
acrescentaria dependências e servidor; uma interface HTML duplicaria decisões de
apresentação nesta etapa. Primeiro valida-se a utilidade e a rastreabilidade da
resposta, que permanece funcional sem IA generativa.

## Qualidade e limitações

`verified` e `complete` nas fixtures são declarações fictícias, não certificados
operacionais. O relatório conserva `authorization_verified=false`, avisos de
qualidade e de atualidade. Não valida que a origem tenha selecionado todos os
jogos elegíveis. Os tokens de versão são referências, não assinaturas verificadas.

O modo demonstração não pode ser usado para dados de clientes. Não há
autenticação real, autorização, exportação HTTP ou escrita em base. O factual não
usa LLM; a seleção opcional FI-008.2 exige `--with-llm` explícito.
O ambiente local disponível tem Python 3.12.10; o mínimo do projeto permanece
3.14. Os resultados locais não substituem futura validação deste incremento em
Python 3.14. A integração PostgreSQL fica desativada nas verificações locais.

## Futuro AI Analyst e interface

Não é necessário criar outro formato de factos: `FactualReport` e `report_json`
já transportam valores, subtotais, cobertura, motivos, referências e avisos.
O adaptador Ollama FI-008.2 recebe uma versão minimizada desse relatório como
dado estruturado, com regras explícitas: não inventar métricas, não tratar
ausência como zero e citar jogos/versões. A interpretação deve aparecer separada
dos factos, identificada como gerada, sem poder alterar os valores do motor.
Conteúdo fornecido pelo modelo nunca deve conceder autorização ou certificar
qualidade. Falhas, timeout ou ausência de Ollama devem manter esta resposta factual.

Depois de aprovada a experiência, uma interface leve poderá reutilizar o mesmo
relatório: seletor de cenários no topo, resumo de resultados, lista cronológica
de jogos e secções de cobertura e referências. A interface definitiva exigirá
requisitos próprios; ligar dados reais depende primeiro da fronteira autenticada
e da certificação de qualidade, não de trocar simplesmente o caminho da fixture.

## Verificar

```powershell
$env:FOOTBALLIQ_DB_RUN_INTEGRATION = '0'
.\.venv\Scripts\python.exe -m pytest -q -rs
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
```

Os testes da demonstração cobrem cinco/um/zero jogos, `null`, subtotais,
ordenação, datas, referências, avisos, estabilidade, recusa de entradas não
aprovadas, CRLF/LF e execução sem imports de infraestrutura ou ligações de rede.

Validação local FI-008.1, com Python 3.12.10, sem instalar dependências:

```text
pytest: 160 passed, 2 skipped in 2.14s
Ruff check: All checks passed!
Ruff format --check: 32 files already formatted
pip check: No broken requirements found.
git diff --check: sem erros
```

Nesta validação usou-se `-B`, `PYTHONDONTWRITEBYTECODE=1`,
`FOOTBALLIQ_DB_RUN_INTEGRATION=0` e `pytest -p no:cacheprovider -q -rs`.
Os dois skips são os testes PostgreSQL existentes, não os testes da demonstração.
São 16 casos novos aprovados. Python 3.14 e CI remoto deste incremento ficam
pendentes de uma tarefa de publicação autorizada; não foram criados commits ou PRs.
