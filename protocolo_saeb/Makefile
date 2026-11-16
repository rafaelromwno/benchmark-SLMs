# Ordem de execução. Nada roda sozinho: cada alvo é um passo explícito.
# Com ~16 GB de RAM: gerador (Qwen, ~3 GB) e juiz (gpt-oss:20b, ~13 GB) NÃO ficam no ar ao mesmo tempo.
#   make servidor-gerador   (terminal 1)   ->   make gerar estrutura   ->   Ctrl+C no servidor
#   make juiz-iniciar   ->   make juiz-testar geval
SHELL := /bin/bash
PY ?= .venv/bin/python
GGUF ?= modelos/Qwen3-4B-Q4_K_M.gguf
LORA ?= modelos/lora_4b_v7b_s44.f16.gguf   # copie do repositório do modelo (gguf/)
GEN_URL ?= http://127.0.0.1:8080
JUIZ_MODELO ?= gpt-oss:20b
JUIZ_URL ?= http://localhost:11434/v1
ESFORCO ?= low
PROFESSORES ?= P1 P2 P3
MODELO_INFO ?= Qwen3-4B-Q4_K_M + lora_4b_v7b_s44 (sha256 no model card)

.PHONY: setup baixar-qwen verificar test servidor-gerador gerar estrutura juiz-iniciar juiz-testar geval amostra analisar

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

juiz-iniciar:     ## sobe o Ollama (feche o servidor-gerador antes)
	OLLAMA_KEEP_ALIVE=30m ollama serve

juiz-testar:      ## sanidade: questão boa x ruim
	cd scripts && ../$(PY) 00_testar_juiz.py --juiz-url $(JUIZ_URL) --juiz-modelo $(JUIZ_MODELO) --esforco $(ESFORCO)

geval:            ## G-Eval nas questões estruturalmente válidas (retoma)
	cd scripts && ../$(PY) 03_geval.py --juiz-url $(JUIZ_URL) --juiz-modelo $(JUIZ_MODELO) --esforco $(ESFORCO)

amostra:          ## planilhas cegas dos professores
	cd scripts && ../$(PY) 04_amostra_humana.py --professores $(PROFESSORES)

analisar:
	cd scripts && ../$(PY) 05_analisar.py
