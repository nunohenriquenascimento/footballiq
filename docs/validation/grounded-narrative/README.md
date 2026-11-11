# Ensaios da seleção de narrativa Ollama

Resultados medidos em 11/11/2026, Windows, Python 3.12.10, Ollama 0.40.16,
RTX 3060 12 GB. Python 3.14 não foi validado localmente; consultar o CI do PR.
Os resultados não são um benchmark geral nem certificam análise tática.

## Método e confiança

Usaram-se apenas as fixtures aprovadas `complete_five`, `partial_match` e `empty`.
O backend real produz FactualReport, tendências e EvidenceBundle. O modelo recebe
apenas um catálogo de planos fechados e escolhe `plan_id`; não cria o plano
completo, frases, números ou referências. O validador aprova o plano inteiro
antes do renderer determinístico. Cada aprovação usa uma observação de golos
marcados num jogo, com amostra 1 e cobertura 1/número de jogos selecionados.

Mede-se wall-clock com `perf_counter`. Os contadores Ollama de carregamento,
prefill e geração são guardados em nanossegundos, sem reinterpretar as medições.
*Frio* significa modelo ausente de `/api/ps` antes do pedido; *quente* significa
presente e não garante que todas as caches e kernels estejam preparados.

## Campanha inicial: fallback

Gemma fez três chamadas `complete_five`, todas com timeout entre 5,005 e 5,030 s.
Qwen fez uma chamada, com timeout em 5,005 s. Não houve resposta JSON observável.
Para cada modelo, `partial_match` e `empty` evitaram a rede, com
`no_verified_facts` e `no_facts`. O factual, tendências e bundle mantiveram-se
iguais nos oito ensaios; zero planos ou referências aceites.

## Diagnóstico e primeiros planos

| Ensaio | Wall (s) | Resultado |
| --- | ---: | --- |
| Gemma mínimo frio, orçamento 5 s | 5,010876 | timeout em cabeçalhos |
| Gemma mínimo ainda ausente, orçamento 15 s | 15,011571 | timeout em cabeçalhos |
| Gemma warmup explícito, já residente | 0,007936 | `done_reason=load` |
| Gemma mínimo quente, orçamento 30 s | 0,296479 | JSON/schema válidos |
| Gemma plano quente, orçamento 5 s | 0,413270 | aprovado |
| Gemma plano quente, orçamento 5 s | 0,132729 | aprovado |
| Qwen mínimo frio, orçamento 30 s | 21,256460 | JSON/schema válidos |
| Qwen mínimo quente, orçamento 5 s | 0,311952 | JSON/schema válidos |
| Qwen plano quente, orçamento 30 s | 0,236278 | aprovado |
| Qwen plano, transporte/defaults originais | 0,371249 | aprovado |
| Gemma plano, transporte/defaults originais | 0,122864 | aprovado |

Qwen frio: carregamento 8,356323 s, prefill 12,806632 s, geração 0,084946 s.
O prefill prepara o estado do modelo a partir do prompt. A preparação inicial
superou o timeout de 5 s. Os timeouts Gemma precederam os cabeçalhos, excluindo
parsing JSON nesses dois casos, mas não têm métricas para decompor a demora.
Também não se conhece a decomposição exata dos quatro timeouts da campanha inicial.

O único warmup explícito foi Gemma; já estava residente antes desse pedido.
Não se atribui ao warmup um carregamento que não mediu. Conteúdo vazio é esperado
no warmup: a classificação inicial de JSON=false nesse registo não representa
uma falha de geração, pelo que se marca o schema como não aplicável no agregado.
Qwen foi aquecido pelo seu primeiro pedido mínimo concluído. Sem descarregamentos,
arranque de serviços, unload ou retries silenciosos.

**Gemma 3/3 e Qwen 2/2 planos aprovados.** As cinco seleções foram `plan:1`,
correspondente a `match:10`, snapshot `synthetic-five-v1`. O modelo não controla
o fact_id ou evidence_id. As cinco chamadas preservaram factual, tendências e
bundle; o renderer repetiu o mesmo texto e só usou referências autorizadas.

O prompt narrativo contém 565 caracteres / 576 bytes UTF-8 e schema de 181 bytes;
payload completo de 1021 bytes Gemma ou 1018 Qwen. A API contou 192/190 tokens
de prompt e 11/10 tokens gerados, respetivamente. O limite continua em 512 tokens.

## Limitações e recomendação

Os cinco planos selecionaram o jogo mais recente, sem diversidade observada.
Não há vantagem de qualidade demonstrada de Qwen neste catálogo restrito.
Gemma é suficiente para a demonstração com modelo carregado. A medição de VRAM
foi aproximadamente 0,302 GiB Gemma e 2,962 GiB Qwen; não extrapolar para contextos
maiores ou outras cargas.

O produto mantém **5 s por operação / prazo cooperativo 15 s**. Os transportes
de diagnóstico usaram explicitamente 5, 15 ou 30 s; não alteraram os defaults.
O parser HTTP e transportes injetados não têm garantia de cancelamento rígido.
O timeout do cliente não prova cancelamento imediato do trabalho no servidor.
Um perfil de demonstração a frio até 30 s e warmup voluntário é proposta para
revisão futura, não uma funcionalidade deste PR. Não há suporte universal a frio.

## Seleção dos artefactos publicados

[results.json](results.json) agrega as duas campanhas, com allowlist de campos:
modelo, cenário, estado, duração, contadores, validação, identidades sintéticas
e invariância. Os valores das medições são copiados dos originais sem arredondar
ou alterar resultados. Campos não observáveis continuam `null`; ausência de
chamada não é falha de schema. Os cinco pares de hashes factuais coincidem.

Não se publicam os 33 originais: baselines já reproduzíveis pelas fixtures,
payloads repetidos, inventários, caminhos absolutos, metadados pessoais e outputs
locais de ferramentas. Os dois scripts históricos exportam inventário/metadados
e foram preservados localmente, em vez de duplicados ou publicados sem revisão.
Nenhum original foi apagado ou modificado nesta preparação.

Para reproduzir offline, executar os testes; para um ensaio real posterior,
executar **manualmente**, com modelo instalado e serviço iniciado pelo utilizador:

```powershell
python -m pytest tests/test_grounded_narrative_orchestrator.py tests/test_grounded_narrative_contract.py -q
python -m footballiq.analyst_demo --fixture complete_five
python -m footballiq.analyst_demo --with-narrative --fixture complete_five --model gemma3:270m
```

A preparação do PR não executou novas inferências, nem alterou modelos ou limites.
