# Derivação para 4 alternativas (A–D)

160 questões geradas com 5 alternativas viraram 4, **sem descartar nenhuma**. A geração original (`questoes.jsonl`) não é alterada; as questões avaliadas são as de `questoes_saeb4.jsonl`, cada uma com o registro da transformação (`transformacao`).

## Alternativa removida

| Motivo | Questões |
|---|---|
| letra_E | 114 |
| nenhuma_das_alternativas | 24 |
| distrator_mais_distante_da_chave | 17 |
| alternativa_repetida | 3 |
| distrator_sorteado | 2 |

## Gabarito por letra, antes e depois

| Ano | Antes A/B/C/D/E | Depois A/B/C/D |
|---|---|---|
| 1º | 14/10/3/8/5 | 10/10/10/10 |
| 2º | 14/7/12/6/1 | 10/10/10/10 |
| 5º | 15/8/8/3/6 | 10/10/10/10 |
| 9º | 16/7/2/9/6 | 10/10/10/10 |
| Todos | 59/32/25/26/18 | 40/40/40/40 |

## Restrições e salvaguardas

- Ordem monotônica preservada (a chave não pôde ser movida): 35.
- "Nenhuma das alternativas" mantida e fixada em D: 0.
- Resoluções com letra reescrita: 0; a revisar manualmente: 0.
- Texto da chave inalterado e alternativas protegidas (chave e resultado da resolução) mantidas: verificado em todas as 160.
- Veredito da verificação aritmética antes e depois: mudou em 0 de 160.
