# Como rodar o G-Eval

Avalia as 120 questões geradas com o juiz `gpt-oss:20b` (Ollama), nos 5 critérios de `config/criterios.json`:
**120 × 5 = 600 chamadas, ~22 s cada, cerca de 3,7 horas** no hardware de referência (~16 GB de RAM; o tempo varia com CPU/GPU). Os resultados vão para
`dados/avaliacao_auto/geval.jsonl` (uma linha por questão e critério). O script **retoma de onde parou**.

## O que é o G-Eval aqui

Um LLM (o juiz) lê a questão e segue **passos de avaliação fixos** (`passos_geval`, um conjunto por critério),
devolvendo uma nota de 0 a 10 e uma justificativa. O DeepEval normaliza a nota para 0–1; o protocolo multiplica
por 10 e converte em 1–5 pelas faixas do artigo-base: [0,1]→1, (1,3]→2, (3,5]→3, (5,7]→4, (7,10]→5.
Aprovado = nota ≥ 4. Detalhes e desvios declarados: `PROTOCOLO.md`, §5.

## Antes de começar

1. **Só um modelo grande por vez.** O juiz ocupa ~13 GB. Se o `llama-server` (gerador) estiver no ar, desligue:
   ```bash
   pkill -f llama-server
   ```
2. **Ambiente pronto** (se for a primeira vez no computador):
   ```bash
   cd protocolo_saeb
   make setup          # cria .venv (Python 3.12 recomendado)
   make verificar      # tudo deve aparecer como [OK]
   ```
3. **Ollama no ar** com o modelo baixado. Em um terminal separado, deixe aberto:
   ```bash
   make juiz-iniciar   # ollama serve, modelo fica 30 min na memória entre chamadas, contexto de 8192 tokens
   ```
   O contexto de 8192 tokens (`OLLAMA_CONTEXT_LENGTH`) é necessário: com o padrão de 4096, o juiz pode estourar a
   janela em itens que o fazem raciocinar muito, devolver resposta vazia e abortar a rodada. Alguns itens levam
   mais de 3 minutos por chamada.
   Se for a primeira vez: `ollama pull gpt-oss:20b` (~13 GB).
4. **Impeça o computador de suspender** durante as ~4 h (macOS: `caffeinate -i`; Linux: `systemd-inhibit`; Windows: plano de energia "nunca suspender").

## Passo a passo

### 5. Teste de sanidade do juiz (~1 min)

```bash
make juiz-testar
```

Manda duas questões-sonda (uma correta, outra com gabarito errado) e exige que a boa tire nota ≥ 4 e a ruim ≤ 2.
Deve terminar com `JUIZ OK`. Se terminar com `JUIZ NÃO DISCRIMINA`, **não rode o G-Eval**: veja "Problemas".

### 6. Rodar o G-Eval nas 120 questões

Em segundo plano, com log (prefixe com o inibidor de suspensão do passo 4, ex. `caffeinate -i`):

```bash
cd protocolo_saeb
nohup make geval > logs/geval.log 2>&1 &
```

O alvo `make geval` usa `gpt-oss:20b`, esforço de raciocínio `low` e o endpoint `http://localhost:11434/v1`.
Para mudar: `make geval JUIZ_MODELO=... JUIZ_URL=... ESFORCO=medium` (mudar o esforço é um desvio do protocolo:
registre no artigo e **não misture** notas de esforços diferentes no mesmo arquivo).

### 7. Acompanhar

```bash
wc -l dados/avaliacao_auto/geval.jsonl     # chega a 600
tail -3 logs/geval.log                      # imprime o item_id de cada questão concluída
```

### 8. Interromper e retomar

Pode interromper a qualquer momento (`pkill -f 03_geval.py`). Para retomar, rode o mesmo comando do passo 6:
pares (questão, critério) já gravados são pulados.

### 9. Conferir o resultado

```bash
.venv/bin/python - <<'E'
import sys; sys.path.insert(0, "scripts")
from comum import *
from collections import Counter
rs = ler_jsonl(DADOS / "avaliacao_auto" / "geval.jsonl")
print(len(rs), "linhas (esperado 600)")
for c in CRITERIOS:
    notas = Counter(r["nota_1a5"] for r in rs if r["criterio"] == c["id"])
    print(c["id"], dict(sorted(notas.items())))
E
make analisar        # aprovação por ano, operação e célula (a parte humana só aparece depois dos professores)
```

Cada linha do `geval.jsonl` tem: `item_id`, `criterio`, `score_0a10`, `nota_1a5`, `justificativa`, `juiz`.
Leia algumas justificativas, principalmente de notas altas em questões sabidamente erradas.

## Rodar só parte dos critérios

Útil para um primeiro passe mais rápido (2 critérios = 240 chamadas, ~1,5 h):

```bash
cd scripts && ../.venv/bin/python 03_geval.py --juiz-url http://localhost:11434/v1 \
  --juiz-modelo gpt-oss:20b --esforco low --criterios intencao_uso correcao_matematica
```

Depois rode `make geval` normalmente para completar os outros três.

## Problemas

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `Connection refused` em `localhost:11434` | Ollama não está no ar | `make juiz-iniciar` em outro terminal |
| `model 'gpt-oss:20b' not found` | modelo não baixado | `ollama pull gpt-oss:20b` |
| Muito lento ou máquina travando | `llama-server` ainda no ar, pouca RAM livre | `pkill -f llama-server`, feche apps pesados |
| `JUIZ NÃO DISCRIMINA` | juiz muito leniente ou outro modelo/esforço | não avalie; revise `passos_geval` **usando só as sondas** de `00_testar_juiz.py`, nunca as 120 questões |
| Erro de validação JSON do DeepEval | o juiz não devolveu o JSON pedido (em geral, contexto de 4096 estourado) | suba o Ollama com `make juiz-iniciar` (8192) e rode de novo (retoma) |
| `FALHA <item> <critério>` no log | o par foi pulado e não tem linha em `geval.jsonl` | rode `make geval` de novo; só os pares faltantes são refeitos |
| Notas todas 5 ou todas 1 | juiz não está seguindo os passos | olhe as justificativas de 5 itens e revise antes de continuar |

## Importante

- **Não edite** `config/criterios.json` (passos), o modelo do juiz ou o esforço no meio de uma rodada: as notas
  deixam de ser comparáveis. Se precisar mudar, apague `dados/avaliacao_auto/geval.jsonl` e recomece.
- Registre no artigo: modelo e versão do juiz (`ollama show gpt-oss:20b`), `reasoning_effort`, temperatura 0 e que
  não há ponderação por log-probabilidade (desvio do G-Eval original).
- O loop completo já foi executado: 600 pares (120 questões × 5 critérios), sem falhas. A rodada foi retomada uma
  vez (370 pares com contexto de 4096, 230 com 8192); ver `PROTOCOLO.md`, §5.
