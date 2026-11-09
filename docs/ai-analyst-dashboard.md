# FI-008.3 — Dashboard visual local

HTML autónomo do FootballIQ AI Analyst, exclusivamente com as fixtures fictícias
aprovadas. Não há servidor HTTP, JavaScript, CDN, fontes remotas ou dependências
novas. O relatório mantém-se consultável offline depois de ser gerado.

## Criar e abrir

Na raiz do checkout completo, com o pacote instalado em modo editável:

```powershell
# Gera num ficheiro temporário e apresenta o caminho. Não abre o browser.
.\.venv\Scripts\python.exe -m footballiq.analyst_demo --html

# Gera e abre o ficheiro local no navegador, por pedido explícito.
.\.venv\Scripts\python.exe -m footballiq.analyst_demo --html --open

# Destino explícito, fora do repositório.
.\.venv\Scripts\python.exe -m footballiq.analyst_demo --html --output "$env:TEMP\footballiq-complete.html"

# Outros cenários sintéticos.
.\.venv\Scripts\python.exe -m footballiq.analyst_demo --html --fixture partial_match --output "$env:TEMP\footballiq-partial.html"
.\.venv\Scripts\python.exe -m footballiq.analyst_demo --html --fixture empty --output "$env:TEMP\footballiq-empty.html"

# Seleção opcional de factos, apenas com um modelo já instalado.
.\.venv\Scripts\python.exe -m footballiq.analyst_demo --html --with-llm --model gemma3:270m --open
```

Em Linux/macOS, usar `.venv/bin/python` e um caminho temporário do sistema.
Sem `--html`, a CLI de terminal conserva o seu comportamento anterior. Não é
preciso configurar base de dados. O modelo indicado é um exemplo instalado no
ensaio FI-008.2.1; a disponibilidade noutra máquina não é presumida.

O HTML é um snapshot, não uma aplicação que consulta serviços ao abrir. Para
trocar de cenário ou atualizar a interpretação, gerar outro ficheiro. A seleção
Ollama ocorre em Python antes da escrita e só com `--with-llm`; o browser não
contacta Ollama. Sem opt-in, a geração é inteiramente offline.

## Política de escrita

Por defeito, cada execução cria um novo `footballiq-demo-*.html` no diretório
temporário do sistema. Não se guardam relatórios em diretórios versionados.
O ficheiro permanece disponível para leitura; pode ser removido pelo utilizador
quando deixar de ser necessário ou pela limpeza normal do sistema.

`--output` exige extensão `.html` e diretório já existente. Um destino existente
é recusado sem alteração de conteúdo. Para o substituir intencionalmente:

```powershell
.\.venv\Scripts\python.exe -m footballiq.analyst_demo --html --output "$env:TEMP\footballiq-complete.html" --overwrite
```

Links simbólicos não são aceites. `--output`, `--overwrite` e `--open` exigem
`--html`. Não existe abertura automática; se a abertura explícita falhar, o
ficheiro gerado permanece disponível e a CLI indica que deve ser aberto manualmente.

## Experiência visual

Identidade em azul escuro e verde-lima, fundo claro, cartões discretos e
tipografia do sistema. A navegação local liga visão geral, jogos, estatísticas,
AI Analyst e referências. Em ecrãs pequenos passa para o topo e os cartões
reorganizam-se em colunas. Não há imagens ou bibliotecas externas.

- Pergunta: «Analisa os últimos cinco jogos da minha equipa.»
- Indicação persistente de **DADOS FICTÍCIOS** e resumo factual da seleção.
- Cartões de vitórias, empates, derrotas, golos a favor e contra, derivados
  diretamente de `report.metrics['competitive']`.
- Sequência V/E/D/? com legenda textual e cor funcional, sem depender só da cor.
- Jogos em ordem recebida do motor, com data/hora UTC, casa/fora, adversário,
  resultado na perspetiva da equipa e estado declarado do resultado.
- Estatísticas, médias, cobertura n/N, subtotais explicitamente identificados
  e motivos por jogo quando o total está indisponível.
- Avisos de qualidade, snapshot, versão das fórmulas e detalhes de cada jogo.

O exemplo completo mostra duas vitórias, dois empates, uma derrota e quatro
golos a favor/contra. O parcial mostra um jogo, cinco cartões de resumo sem
valores e cobertura competitiva 0/1. O vazio mostra zero jogos, sem resultados,
totais ou médias, e cobertura 0/0. Não se transforma `null` em zero. Pontos
oficiais não são calculados sem regulamento validado.

As referências expansíveis mostram `data_version`, IDs de eventos, fonte e
proveniência. Nas observações AI aceites, as referências ligam aos jogos da
mesma página. `Tab` navega pelos links e `Enter` abre/fecha os detalhes; existe
atalho para saltar para o conteúdo, foco visível e suporte a movimento reduzido.

## IA separada dos factos

- `not_requested`: não foi solicitado modelo; todo o relatório factual está visível.
- `available`: a seleção estruturada passou a validação existente e o renderer
  reconfirmou o texto e as referências no catálogo determinístico.
- `unavailable`: configuração, timeout, resposta inválida ou ausência de jogos;
  o aviso é apresentado sem ocultar o factual.

Não se admite prosa livre do modelo. Os textos e números são locais e derivados
do relatório; não representam raciocínio tático avançado. Ver as regras completas
em [FI-008.2](ollama-analyst.md) e o [ensaio real](ollama-validation.md).

## Implementação e segurança

`analyst_dashboard.py` separa apresentação e escrita. `render_dashboard` consome
`FactualReport` e, opcionalmente, `InterpretationResult`; não recalcula métricas.
`save_dashboard` implementa a política de destino. A CLI acrescenta apenas opções
explícitas e reutiliza a mesma seleção validada para terminal e HTML.

Todos os campos dinâmicos passam por `html.escape(..., quote=True)`. Não se
insere JSON em scripts, não se usam `innerHTML`, URLs da origem ou CSS dinâmico.
Os únicos links são âncoras locais com IDs gerados pelo código. CSP bloqueia
scripts, ligações, imagens, formulários e outras fontes externas; permite só o
CSS embebido. O escape e a revalidação da interpretação são testados também com
conteúdo malicioso fictício.

A CLI mantém o carregador fechado e os hashes das fixtures. O filtro de origem
fictícia do renderer não é uma fronteira de autenticação. O HTML não prova
autorização, autenticidade, qualidade operacional ou atualidade. Não se alteraram
ORM, persistência, migrações, contratos v1, Match Tracker ou SUB-19.

## Validação FI-008.3

Ambiente: Windows, Python 3.12.10. Python 3.14 continua por validar para este
incremento. Sem novas dependências, servidor, PostgreSQL ou pedidos reais a Ollama.

```text
python -B -m pytest -p no:cacheprovider -q -rs
245 passed, 2 skipped in 3.31s

ruff check --no-cache .
All checks passed!

ruff format --check --no-cache .
39 files already formatted

python -m pip check
No broken requirements found.

git diff --check
sem erros
```

Usou-se `FOOTBALLIQ_DB_RUN_INTEGRATION=0` e `PYTHONDONTWRITEBYTECODE=1`.
Os dois skips são os testes PostgreSQL existentes. Foram acrescentados 27 casos
offline para conteúdo, nulls, cobertura, referências, datas, escaping, estados AI,
escrita/sobrescrita, abertura explícita, estrutura responsiva e geração sem SQL.

Geraram-se os três HTML em diretório temporário. A inspeção com Edge headless e
Playwright já existente verificou desktop 1440×1000 e telemóvel 390×844: cinco,
um e zero jogos corretos, zero scripts, zero pedidos HTTP externos e ausência
de scroll horizontal. Os detalhes responderam a Enter. Guardaram-se capturas
temporárias desktop e mobile; não são artefactos versionados. Não é uma auditoria
completa de acessibilidade ou de todos os navegadores.

## Limitações e evolução

Requer checkout com as fixtures; uma wheel isolada não as contém. O HTML é local
e estático, sem autenticação, troca de fixture dentro da página ou atualização
automática. A escolha por HTML evita instalar um framework ou servidor apenas
para esta demonstração. Não se modifica o motor factual nem se duplicam fórmulas.

Próximo incremento: revisão visual e de usabilidade, validação Python 3.14 e,
se autorizada, publicação da branch para CI. A interface definitiva com dados
reais depende de autenticação, autorização por recurso e qualidade operacional;
não basta remover o aviso de demonstração ou trocar o caminho das fixtures.

## Revisão FI-008.3.1 — visual e acessibilidade

A revisão manteve a arquitetura e a paleta. Foram reproduzidos e corrigidos:

- Nomes/avisos sem espaços causavam scroll horizontal: o texto agora pode quebrar
  sem truncar o conteúdo. Identificadores e versões permanecem completos.
- A sequência não quebrava de linha e o resultado indisponível era forçado a uma
  linha: o zoom de 200% em mobile podia exceder a largura disponível. Ambos adaptam
  a largura; a barra lateral permite deslocação vertical em janelas baixas.
- O atalho para o conteúdo deslocava a página mas não transferia foco: `main`
  tem agora `tabindex=-1`, sem acrescentar uma paragem à sequência normal de Tab.
- Referências fechadas eram omitidas na impressão: o conteúdo de `details` passa
  a ficar visível em modo print, sem abrir os detalhes no ecrã ou executar scripts.
- Os símbolos V/E/D/? tinham labels sobre spans genéricos: receberam papel de
  imagem, com nome acessível explícito. A legenda textual permanece visível.
- Na inspeção a 200%, a marca e o aviso de dados fictícios quebravam de forma
  ilegível: a marca é um grupo sem quebra e a barra superior permite reorganizar
  os elementos em linhas diferentes. Não se diminuiu o tamanho de letra do zoom.

Há um `h1`, um `main`, navegação identificada e headings sem saltos de nível.
Os contrastes dos pares de texto principais medidos ultrapassaram 4,5:1; as
vitórias/empates/derrotas também possuem letras, legenda e nomes acessíveis.
Referências: [contraste mínimo W3C](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
e [redimensionamento de texto W3C](https://www.w3.org/WAI/WCAG22/Understanding/resize-text.html).
Os testes não constituem uma certificação WCAG completa.

### Regressões e resultado

Acrescentaram-se dois testes: um verifica a semântica do atalho e os nomes da
sequência recebida do motor; outro é uma regressão opcional de navegador real.
Esta última precisa apenas de Node, Edge e um módulo Playwright **já instalado**.
Não instala dependências nem altera ficheiros dessa ferramenta.

```powershell
# Apenas se essa ferramenta já existir: indicar o caminho local do módulo.
$env:FOOTBALLIQ_PLAYWRIGHT_MODULE = 'CAMINHO_ABSOLUTO_PARA_PLAYWRIGHT_EXISTENTE'
$env:FOOTBALLIQ_DB_RUN_INTEGRATION = '0'
$env:PYTHONDONTWRITEBYTECODE = '1'
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q -rs
```

Sem essa variável, a regressão de navegador é explicitamente ignorada; os restantes
testes continuam independentes de browser. No ensaio final, com browser disponível:

```text
247 passed, 2 skipped in 5.11s
All checks passed!
40 files already formatted
No broken requirements found.
git diff --check: sem erros
Python 3.12.10
```

Os dois skips continuam a ser exclusivamente PostgreSQL. Uma primeira execução
encontrou `PermissionError` na pasta pytest temporária partilhada; a repetição
usou `--basetemp` num diretório novo e exclusivo do sistema temporário, sem tocar
na pasta problemática. Não se alterou código para contornar esse problema ambiental.

O navegador verificou complete_five, partial_match, empty e conteúdo fictício
adicional com nomes/identificadores extensos, em 1440×900 e 390×844, a 100% e com
`zoom:2` no elemento raiz. Essa ampliação CSS exercita o dobro do tamanho, mas
não equivale a testar manualmente todos os modos de zoom nativos dos browsers.
Não houve scroll horizontal; o foco do atalho chegou a `main`; Tab/Enter e
details/summary funcionaram; as referências fechadas ficaram visíveis ao imprimir.
Também se guardaram capturas e um PDF temporários para inspeção visual.

A sequência da fixture completa foi V,V,E,D,E, na mesma ordem dos jogos
10,9,8,7,6. Os cenários parcial/vazio mantêm `null` como indisponível. Os testes
existentes de escape, IA validada, output exclusivo, `--overwrite`, `--open`,
ausência de SQL e zero rede continuam aprovados. Nenhum pedido real a Ollama.

### Prontidão

A branch está tecnicamente pronta para revisão do diff e preparação de commit/CI
autorizados. Python 3.14 ainda não foi executado neste incremento e deve ser
validado pelo CI antes de integrar. Não se criaram commits, pushes ou PRs nesta
revisão. Permanecem as limitações de dados sintéticos, HTML estático e ausência
de autenticação/autorização operacional; faltam ensaios com leitores de ecrã e
outros navegadores. Não se redesenhou a aplicação nem se alteraram os contratos.
