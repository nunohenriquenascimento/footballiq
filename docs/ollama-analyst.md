# FI-008.2 — Seleção de observações com Ollama

A demonstração continua a responder sem LLM. Ollama é opcional e só seleciona
e ordena factos conhecidos; não escreve prosa livre nem calcula métricas.
Usam-se exclusivamente as fixtures fictícias aprovadas em FI-008.1.

## Execução

```powershell
# Sem LLM: comportamento FI-008.1 preservado.
.\.venv\Scripts\python.exe -m footballiq.analyst_demo

# Opt-in: usar o nome exato de um modelo que já esteja instalado.
.\.venv\Scripts\python.exe -m footballiq.analyst_demo --with-llm --model qwen3:8b

# Servidor local noutra porta; apenas HTTP de loopback.
.\.venv\Scripts\python.exe -m footballiq.analyst_demo --with-llm --model qwen3:8b --ollama-url http://127.0.0.1:11435

# Os cenários FI-008.1 continuam disponíveis.
.\.venv\Scripts\python.exe -m footballiq.analyst_demo --fixture partial_match --with-llm --model qwen3:8b
.\.venv\Scripts\python.exe -m footballiq.analyst_demo --fixture empty --with-llm --model qwen3:8b
```

`qwen3:8b` é apenas um exemplo, não uma confirmação de instalação. Não há download
automático, instalação de serviços ou leitura de credenciais. Sem `--model`, o
modo LLM mostra aviso de configuração e conserva o factual. Os testes não precisam
de Ollama; nesta tarefa não se contactou qualquer servidor real.

## Arquitetura

- `analyst_demo.py`: carrega a fixture aprovada, produz primeiro o factual e só
  acrescenta a secção opcional com `--with-llm`.
- `analyst_interpretation.py`: minimiza o `FactualReport`, constrói um catálogo
  de frases determinísticas e valida a seleção do modelo.
- `ollama_client.py`: HTTP da biblioteca padrão para `POST /api/chat`, com schema
  JSON, `stream=false`, `think=false`, temperatura 0 e máximo de 512 tokens.
  Não foram acrescentadas dependências.

Segue a documentação oficial de [chat](https://docs.ollama.com/api/chat) e
[structured outputs](https://docs.ollama.com/capabilities/structured-outputs).
O schema orienta a geração; a validação local continua obrigatória.

## Contexto e resposta

O contexto inclui IDs, datas, versões, resultados, métricas, subtotais, cobertura,
referências e códigos de limitações. `null` permanece `null`. Não contém nomes
de jogadores/adversários, scope, paths, credenciais ou texto livre da origem.
Avisos enviados são frases locais fechadas e motivos são códigos conhecidos;
versões de sintaxe inválida causam fallback antes do pedido.

Exemplo de seleção aceite:

```json
{
  "summary": "selection",
  "observations": [
    {
      "fact_id": "metric:competitive",
      "references": ["match:10", "match:9", "match:8", "match:7", "match:6"]
    },
    {"fact_id": "match:10", "references": ["match:10"]}
  ]
}
```

Apresentação correspondente, obtida com cliente simulado:

```text
INTERPRETAÇÃO OPCIONAL — seleção de factos por Ollama
interpretation_status=available
5 jogos selecionados de um máximo de 5. Dados fictícios; qualidade declarada; autorização e atualidade não verificadas. [selection]
- Resultados: vitórias: 2; empates: 2; derrotas: 1; golos marcados: 4; golos sofridos: 4. Cobertura 5/5. [match:10, match:9, match:8, match:7, match:6]
- Jogo 10: 2–1, vitória na perspetiva da equipa. [match:10]
```

Não é uma execução real de Ollama. A escolha e a ordem podem variar com o modelo;
os números e os textos são sempre produzidos pelo código a partir do motor.

## Validação e limites

Pydantic estrito rejeita campos extra, chaves JSON repetidas, constantes não JSON,
IDs desconhecidos, referências erradas/incompletas/repetidas e observações
duplicadas. São aceites 1–5 observações, cada uma com até cinco referências exatas.
O resumo é um identificador fechado. Texto livre, hipóteses, números adicionais
ou métricas inventadas são rejeitados.

`available` significa que a seleção e as referências foram verificadas. Não
significa verificar a verdade de frases livres: nenhuma é aceite ou apresentada.
Não comprova autenticidade ou qualidade operacional. Não há interpretação tática.

O pedido completo tem limite de 32 KiB, verificado antes do transporte. O corpo
HTTP de resposta tem limite de 64 KiB e o conteúdo de 8 KiB. Respostas incompletas,
truncadas, de outro modelo ou com chamadas de ferramentas são recusadas. O cliente
não segue redirects, não usa proxies de ambiente e recusa credenciais no URL.
Só liga a 127.0.0.1 ou ::1. O timeout é de 5 segundos por operação de socket,
configurável no adaptador entre 1 e 10 segundos; não é uma garantia de prazo
absoluto perante um servidor que envie dados lentamente. Um modelo frio pode
ultrapassá-lo. Não se repete o pedido automaticamente.

Servidor desligado, timeout, falta de modelo ou resposta não verificável produzem
fallback. Exemplo:

```text
interpretation_status=unavailable
Modelo não encontrado; escolha um modelo já instalado.
O relatório factual acima mantém-se integralmente disponível.
```

Nunca se imprime o corpo de erro, texto bruto do modelo ou detalhes internos da
exceção. Sem jogos, não há pedido. Dados parciais permitem apenas factos limitados,
como «Remates: total indisponível. Cobertura 0/1.», sem preencher valores ausentes.

## Preservação e segurança

O `FactualReport` não é alterado. O seu `interpretation_status=not_requested`
continua a descrever o motor factual. `available/unavailable` pertence ao objeto
`InterpretationResult` separado, apresentado depois do factual. Sem opt-in, a
resposta FI-008.1 permanece igual e nenhum cliente é construído.

A CLI mantém a lista fechada e os hashes das fixtures. O adaptador recusa identidade
operacional, mas esse filtro não é autenticação; não deve ser exposto como fronteira
de produção. A proteção não depende apenas de o modelo obedecer ao prompt:
minimização, vocabulário fechado e renderização determinística impedem transformar
texto recebido em ações. Não existem ferramentas, execução de SQL/código,
autorização real ou API pública.

## Verificação e evolução

```powershell
$env:FOOTBALLIQ_DB_RUN_INTEGRATION = '0'
.\.venv\Scripts\python.exe -m pytest -q -rs
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
```

Os testes usam transporte/cliente falso: erros HTTP, timeout, modelo ausente, JSON
inválido, referências inventadas, números não fundamentados, duplicados, limites,
prompt injection, dados parciais, ausência de jogos, estabilidade e imports sem SQL.
Não contactam Ollama ou PostgreSQL.

Validação local final FI-008.2 (inclui os casos FI-008.1 preservados):

```text
214 passed, 2 skipped in 2.71s
All checks passed!
36 files already formatted
No broken requirements found.
```

Comandos efetivos: `python -B -m pytest -p no:cacheprovider -q -rs`,
`ruff check --no-cache .`, `ruff format --check --no-cache .`, `python -m pip check`
e `git diff --check` (sem erros). Integração PostgreSQL desativada explicitamente;
os dois skips são os testes de base de dados existentes. Há 54 novos casos offline
para FI-008.2. Não foram criados commits, pushes ou PRs.

Python local: 3.12.10; mínimo do projeto: 3.14. Os testes deste incremento em
Python 3.14 continuam pendentes. O [ensaio real FI-008.2.1](ollama-validation.md)
regista sucesso com `gemma3:270m`, timeouts com `qwen3:4b` e preservação factual.
Esses resultados não demonstram qualidade de geração com outros modelos.

Próximo incremento: interface leve sobre os factos e estados já validados. Avaliar
outros modelos em tarefa própria antes de considerar prosa generativa, com
verificação independente e interface que preserve factos, cobertura e referências.
Dados reais continuam dependentes de autenticação, autorização e qualidade operacionais.
