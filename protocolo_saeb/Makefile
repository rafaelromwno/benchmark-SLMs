# Ordem de execução. Nada roda sozinho: cada alvo é um passo explícito.
# Com ~16 GB de RAM: gerador (Qwen, ~3 GB) e juiz (gpt-oss:20b, ~13 GB) NÃO ficam no ar ao mesmo tempo.
#   make servidor-gerador   (terminal 1)   ->   make gerar estrutura   ->   Ctrl+C no servidor
#   make aritmetica contaminacao TREINO=...   (sem modelo, rodam a qualquer momento)
#   make juiz-iniciar   ->   make juiz-testar geval   ->   make congelar (sela o juiz antes da coleta humana)
SHELL := /bin/bash
PY ?= .venv/bin/python
GGUF ?= modelos/Qwen3-4B-Q4_K_M.gguf
LORA ?= modelos/lora_4b_v7b_s44.f16.gguf   # copie do repositório do modelo (gguf/)
GEN_URL ?= http://127.0.0.1:8080
JUIZ_MODELO ?= gpt-oss:20b
JUIZ_URL ?= http://localhost:11434/v1
ESFORCO ?= low
PROFESSORES ?= P1 P2 P3
TREINO ?=
MODELO_INFO ?= Qwen3-4B-Q4_K_M + lora_4b_v7b_s44 (sha256 no model card)

.PHONY: setup baixar-qwen verificar test servidor-gerador gerar estrutura aritmetica contaminacao derivar juiz-iniciar juiz-testar geval congelar amostra analisar taxonomia

setup:            ## cria .venv e instala dependências
	./setup.sh

baixar-qwen:      ## baixa o GGUF base (~2,5 GB) de Qwen/Qwen3-4B-GGUF
	mkdir -p modelos && curl -L -C - -o $(GGUF) https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q4_K_M.gguf

verificar:        ## preflight (não gera nada)
	cd scripts && ../$(PY) 00_verificar_ambiente.py --gguf ../$(GGUF) --lora $(LORA) --juiz-modelo $(JUIZ_MODELO)

test:             ## testes unitários
	$(PY) -m pytest -q tests

servidor-gerador: ## llama-server com base + LoRA (fica em primeiro plano)
	llama-server -m $(GGUF) --lora $(LORA) -c 2048 --port 8080 --threads 8

gerar:            ## 160 questões (retoma se interrompido)
	cd scripts && ../$(PY) 01_gerar.py --url $(GEN_URL) --modelo-info "$(MODELO_INFO)"

estrutura:
	cd scripts && ../$(PY) 02_checar_estrutura.py

aritmetica:       ## verificação aritmética determinística (reporta a cobertura)
	cd scripts && ../$(PY) 02b_verificar_aritmetica.py

derivar:          ## versão de 4 alternativas (A-D), balanceada; precisa de `make aritmetica` antes
	cd scripts && ../$(PY) 09_derivar_4_alternativas.py

contaminacao:     ## similaridade com o treino e entre as questões (TREINO=arquivo.jsonl [outro.jsonl])
	cd scripts && ../$(PY) 02c_contaminacao.py $(if $(TREINO),--referencia $(TREINO),)

juiz-iniciar:     ## sobe o Ollama (feche o servidor-gerador antes)
	OLLAMA_KEEP_ALIVE=30m OLLAMA_CONTEXT_LENGTH=8192 ollama serve

juiz-testar:      ## sanidade: sondas sintéticas (boa, gabarito errado, conta errada)
	cd scripts && ../$(PY) 00_testar_juiz.py --juiz-url $(JUIZ_URL) --juiz-modelo $(JUIZ_MODELO) --esforco $(ESFORCO)

geval:            ## G-Eval nas questões estruturalmente válidas (retoma; só calcula pares que faltam)
	cd scripts && ../$(PY) 03_geval.py --juiz-url $(JUIZ_URL) --juiz-modelo $(JUIZ_MODELO) --esforco $(ESFORCO)

congelar:         ## grava config/CONGELADO.json (hashes e versões; sela o resultado do juiz)
	cd scripts && ../$(PY) 07_congelar.py --juiz-modelo $(JUIZ_MODELO) $(if $(wildcard $(GGUF)),--gguf $(abspath $(GGUF)),) $(if $(wildcard $(LORA)),--lora $(abspath $(LORA)),)

amostra:          ## planilhas cegas dos professores
	cd scripts && ../$(PY) 04_amostra_humana.py --professores $(PROFESSORES)

analisar:
	cd scripts && ../$(PY) 05_analisar.py

taxonomia:        ## causas de reprovação do juiz e dos professores (planilha de codificação)
	cd scripts && ../$(PY) 08_taxonomia.py
