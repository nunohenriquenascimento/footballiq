# FI-009.2.3.1 — Narrativa fundamentada no dashboard local

## Arquitetura e âmbito

A branch `feature/grounded-narrative-dashboard` parte de `origin/main`, no merge
aprovado `e27e1b66136fa6074f4b7317bbf2d8ca113f0cb8`. O worktree original pôde ser
mantido porque não havia alterações rastreadas e a árvore da feature anterior
coincidia com a base. Workspace e artefactos locais foram preservados.

O HTML continua um snapshot autónomo: sem servidor, JavaScript, CDN, chatbot,
RAG ou dependências novas. Só a geração Python, com opt-in explícito, pode
contactar Ollama. Abrir ou expandir detalhes no navegador não executa rede.

`render_demo_dashboard(with_narrative=True)` reutiliza a mesma função privada
de seleção do modo texto e o `narrate_report` existente. A opção antiga
`with_llm` mantém-se disponível, mas não se combina com a nova.
Sem opções, o HTML conserva o conteúdo e estrutura anteriores.

`render_dashboard(report, narrative=result)` não confia no dataclass nem no
seu texto. Reconstrói o EvidenceBundle a partir do relatório, revalida o plano
com GroundedNarrativeValidator e exige igualdade com um candidato emitido por
`prepare_plans`. Esta última verificação impede alterações à cobertura/amostra
ou o uso de outros templates que o validador v1, isoladamente, pudesse aceitar.
O plano é revalidado por serialização JSON para não confiar em instâncias
Pydantic modificadas depois da construção. Texto e referências livres do
NarrativeResult nunca são apresentados.

A observação final usa apenas dados do jogo referido no plano fechado. Não se
altera o catálogo factual, o contrato v1, a política de evidence_id, Analytics,
tendências, ORM ou persistência. As restantes secções do HTML são preservadas.

## Apresentação para treinadores

O painel AI Analyst existente apresenta «Narrativa fundamentada» e um estado
legível: «Disponível · plano verificado», «Indisponível» ou «Não solicitada».
Com o plano sintético `plan:1` da fixture completa, mostra:

> No jogo de 08/11/2026, frente a Equipa Ficticia B, a equipa marcou 2 golos.

O nome e a data vêm do relatório; não são exemplos fixos no código. A observação
tem ligação ao jogo, amostra de 1 jogo e cobertura 1/5 da janela. Esta cobertura
é a da observação selecionada, distinta da cobertura competitiva 5/5 mostrada
nas estatísticas. Não se transforma uma observação no total dos cinco jogos.

Um aviso explica a amostra pequena e a ausência de conclusões táticas, causas
ou previsões. «Detalhes técnicos e evidências» usa `<details>/<summary>` nativos
para consultar fact_id, snapshot, digest, origem, versões e evidence_ids
autorizados. Os identificadores são mantidos integralmente, com quebra de linha
pelas regras CSS existentes. O desenho responsivo, navegação, métricas,
tendências, qualidade e referências anteriores mantêm-se.

## Comandos Windows

Executar na raiz do checkout completo, com o ambiente existente:

```powershell
# Sem IA: não necessita de Ollama nem de modelos.
.\.venv\Scripts\python.exe -m footballiq.analyst_demo --html

# Opt-in real: executar manualmente, com modelo já instalado e serviço ativo.
.\.venv\Scripts\python.exe -m footballiq.analyst_demo --html --with-narrative --model gemma3:270m

# Destino explícito; não substitui ficheiros existentes sem --overwrite.
.\.venv\Scripts\python.exe -m footballiq.analyst_demo --html --with-narrative --model gemma3:270m --output "$env:TEMP\footballiq-narrative.html"

# Estado vazio, sem chamada de inferência (modelo explícito apenas para configuração).
.\.venv\Scripts\python.exe -m footballiq.analyst_demo --html --with-narrative --model gemma3:270m --fixture empty
```

`--with-narrative` não combina com `--with-llm`; `--open`, `--overwrite` e
`--output` continuam a exigir `--html`. Sem `--output`, o gerador escolhe um
ficheiro temporário novo; `--open` é sempre explícito. Nenhum destes comandos
de inferência real foi executado automaticamente nesta tarefa.

Para reproduzir um HTML disponível inteiramente offline, simulando apenas a
seleção do modelo (os factos continuam a vir da fixture aprovada):

```powershell
@'
from unittest.mock import Mock
from footballiq.analyst_demo import render_demo_dashboard
from footballiq.analyst_dashboard import save_dashboard
client = Mock(chat=Mock(return_value='{"plan_id":"plan:1"}'))
print(save_dashboard(render_demo_dashboard(with_narrative=True, client=client)))
'@ | .\.venv\Scripts\python.exe -
```

## Fallback e segurança

Sem opt-in, nenhum cliente é consultado. Sem jogos, não há chamada; resultados
não verificados também não originam observações. Falha de rede, modelo ausente,
timeout, JSON/schema inválido ou plano não verificável mantêm as estatísticas e
tendências e não mostram afirmações rejeitadas. O utilizador vê uma mensagem
local compreensível; códigos desconhecidos e mensagens brutas não são refletidos.

Todos os dados dinâmicos passam por `html.escape(quote=True)`. Os links usam
âncoras locais geradas por índice do jogo. O documento não contém prompts,
respostas brutas, tokens, scripts externos ou `innerHTML`. A CSP mantém
`script-src 'none'` e `connect-src 'none'`. A marca de instalação fictícia é uma
limitação de demonstração, não autenticação operacional.

O cliente Ollama e os limites permanecem intactos: 5 s por operação, prazo
cooperativo de 15 s, sem retries ou warmup automático. Cold start pode causar
fallback. A nova vista não resolve essa limitação nem mede qualidade tática.

## Validação e demonstração

Os testes novos bloqueiam sockets, usam fixtures aprovadas e seleções simuladas.
Cobrem sucesso, indisponibilidade, timeout, JSON/schema inválido, evidência e
snapshot trocados, amostra/cobertura adulteradas, template fora do catálogo,
escaping, janela parcial, ausência de jogos, links locais e compatibilidade CLI.
Comparam o HTML fora do painel AI byte a byte e verificam não mutação do factual,
tendências e bundle. A suite anterior de interpretação e dashboard permanece.

Foram gerados oito HTML sintéticos fora do repositório: completo/parcial/vazio,
cada um sem IA e com seleção simulada, mais timeout e plano inválido. Inspeção
estrutural confirmou ausência de scripts e de texto rejeitado. Não se executou
Ollama real. Playwright não estava configurado nem instalado; não se instalaram
ferramentas. A tentativa de captura com Edge headless não produziu imagem
utilizável: **não se declara inspeção visual nem QA de navegador**.

Na preparação FI-009.2.3.3, o utilizador comunicou que abriu o dashboard real e
forneceu capturas, tendo a revisão visual do ChatGPT aprovado a apresentação.
Esta aprovação visual é a comunicada no contexto da tarefa; o executor não
declara cliques ou interação manual próprios. Sem Playwright configurado, a
verificação funcional do executor usa estrutura e semântica HTML: ligação
«Consultar jogo 10» ao destino `#match-0`, detalhes nativos expansíveis,
referências autorizadas, escaping e fallback. Gráficos e novas observações ficam
fora do âmbito desta publicação.

Os outputs literais e caminhos dos exemplos ficam no registo local
`docs/validation/fi009-2-3-1/checks.json`. Python local 3.12.10; Python 3.14
continua por validar nesta branch. Recomenda-se revisão ChatGPT da clareza da
observação, distinção de coberturas, detalhes expansíveis e fallback. A próxima
verificação visual deve cobrir desktop/mobile, texto longo, teclado e impressão,
sem ampliar o catálogo ou introduzir rede no browser.
