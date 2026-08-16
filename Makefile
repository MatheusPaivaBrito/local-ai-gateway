.DEFAULT_GOAL := help
SHELL := /bin/bash

COMPOSE := docker compose -f compose.yaml
COMPOSE_GPU := docker compose -f compose.yaml -f compose.gpu.yaml
PROFILE := --profile container-gateway

NAME ?= local-dev
KEY ?=
MODEL ?=

.PHONY: help bootstrap prepare-env install gpu-check docker-check \
	infra-up infra-up-gpu infra-down infra-ps infra-logs wait-infra \
	run run-cpu container-up container-up-gpu container-rebuild \
	up up-gpu down ps logs models pull-model rm-model \
	test lint import-check check smoke create-key revoke-key doctor

help:
	@printf '\n%s\n' '------------------------------------------------------------'
	@printf '%s\n' ' Local AI Gateway'
	@printf '%s\n\n' '------------------------------------------------------------'
	@printf '%-20s %s\n' 'make run'              'DEV recomendado: infra no Docker + FastAPI local com --reload/GPU'
	@printf '%-20s %s\n' 'make run-cpu'          'DEV local sem telemetria/GPU no Ollama'
	@printf '%-20s %s\n' 'make bootstrap'        'Valida máquina, instala deps Python e sobe a infra GPU'
	@printf '%-20s %s\n' 'make infra-up-gpu'     'Sobe PostgreSQL, Redis, Qdrant e Ollama com GPU'
	@printf '%-20s %s\n' 'make infra-up'         'Sobe somente a infraestrutura em CPU'
	@printf '%-20s %s\n' 'make infra-down'       'Encerra a infraestrutura'
	@printf '%-20s %s\n' 'make up'               'Sobe TODO o projeto em containers (CPU)'
	@printf '%-20s %s\n' 'make up-gpu'           'Sobe TODO o projeto em containers (GPU NVIDIA)'
	@printf '%-20s %s\n' 'make container-rebuild' 'Rebuild limpo do gateway containerizado'
	@printf '%-20s %s\n' 'make models'           'Lista modelos instalados no Ollama'
	@printf '%-20s %s\n' 'make pull-model'       'Instala modelo. MODEL=qwen3:4b'
	@printf '%-20s %s\n' 'make rm-model'         'Remove modelo. MODEL=qwen3:4b'
	@printf '%-20s %s\n' 'make check'            'Ruff + pytest + import de todas as slices + compileall'
	@printf '%-20s %s\n' 'make doctor'           'Mostra GPU, containers e valida a infraestrutura'
	@printf '\nUI:      http://localhost:8001/ui\n'
	@printf 'Swagger: http://localhost:8001/docs\n'
	@printf 'Qdrant:  http://localhost:6333/dashboard\n\n'

prepare-env:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		printf '%s\n' '.env criado a partir de .env.example.'; \
	else \
		printf '%s\n' '.env existente mantido.'; \
	fi

install: prepare-env
	@command -v poetry >/dev/null 2>&1 || { \
		echo 'ERRO: Poetry não encontrado.'; \
		echo 'Instale o Poetry e execute novamente.'; \
		exit 1; \
	}
	@poetry install --with dev


docker-check:
	@command -v docker >/dev/null 2>&1 || { echo 'ERRO: Docker não encontrado.'; exit 1; }
	@docker info >/dev/null 2>&1 || { echo 'ERRO: daemon Docker indisponível.'; exit 1; }
	@docker compose version >/dev/null


gpu-check: docker-check
	@command -v nvidia-smi >/dev/null 2>&1 || { echo 'ERRO: nvidia-smi não encontrado.'; exit 1; }
	@nvidia-smi -L >/dev/null 2>&1 || { echo 'ERRO: GPU NVIDIA indisponível no WSL/Linux.'; exit 1; }
	@docker run --rm --gpus all alpine:3.20 sh -c \
		'test -e /dev/nvidia0 || test -e /dev/dxg || ls /dev/nvidia* >/dev/null 2>&1' \
		|| { echo 'ERRO: Docker não acessa a GPU.'; exit 1; }

bootstrap:
	@clear
	@printf '\n%s\n' '------------------------------------------------------------'
	@printf '%s\n'   ' LOCAL AI GATEWAY - BOOTSTRAP GPU'
	@printf '%s\n\n' '------------------------------------------------------------'
	@printf '%s\n\n' '[1/8] Verificando NVIDIA GPU...'
	@command -v nvidia-smi >/dev/null 2>&1 || { echo 'ERRO: nvidia-smi não encontrado.'; exit 1; }
	@nvidia-smi -L >/dev/null 2>&1 || { echo 'ERRO: GPU NVIDIA indisponível no WSL/Linux.'; exit 1; }
	@nvidia-smi
	@printf '\n%s\n\n' '[2/8] Verificando Docker...'
	@command -v docker >/dev/null 2>&1 || { echo 'ERRO: Docker não encontrado.'; exit 1; }
	@docker info >/dev/null 2>&1 || { echo 'ERRO: daemon Docker indisponível.'; exit 1; }
	@docker --version
	@printf '\n%s\n\n' '[3/8] Verificando Docker Compose...'
	@docker compose version
	@printf '\n%s\n\n' '[4/8] Verificando acesso do Docker à GPU...'
	@docker run --rm --gpus all alpine:3.20 sh -c \
		'test -e /dev/nvidia0 || test -e /dev/dxg || ls /dev/nvidia* >/dev/null 2>&1' \
		|| { echo 'ERRO: Docker não acessa a GPU.'; exit 1; }
	@printf '%s\n' 'GPU disponível para containers.'
	@printf '\n%s\n\n' '[5/8] Preparando .env...'
	@$(MAKE) --no-print-directory prepare-env
	@printf '\n%s\n\n' '[6/8] Instalando dependências Poetry...'
	@command -v poetry >/dev/null 2>&1 || { echo 'ERRO: Poetry não encontrado.'; exit 1; }
	@poetry --version
	@poetry install --with dev
	@printf '\n%s\n\n' '[7/8] Validando projeto...'
	@$(MAKE) --no-print-directory check
	@printf '\n%s\n\n' '[8/8] Subindo PostgreSQL, Redis, Qdrant e Ollama...'
	@$(COMPOSE_GPU) up -d postgres redis qdrant ollama
	@poetry run python -m scripts.wait_infra
	@printf '\n%s\n' '------------------------------------------------------------'
	@printf '%s\n'   ' INFRAESTRUTURA PRONTA'
	@printf '%s\n'   '------------------------------------------------------------'
	@printf '\n%s\n' 'COMO SUBIR O PROJETO:'
	@printf '%s\n'   '  make run      -> desenvolvimento: FastAPI local + infra Docker GPU'
	@printf '%s\n'   '  make up       -> projeto inteiro em containers (CPU)'
	@printf '%s\n\n' '  make up-gpu   -> projeto inteiro em containers (GPU NVIDIA)'
	@printf '%s\n' 'Para desenvolvimento, use make run: o Uvicorn fica com auto-reload e não exige rebuild.'
	@printf '%s\n\n' 'Nenhum modelo é baixado automaticamente; pesquise e instale pela UI.'

infra-up: install docker-check
	@$(COMPOSE) up -d postgres redis qdrant ollama

infra-up-gpu: install gpu-check
	@$(COMPOSE_GPU) up -d postgres redis qdrant ollama

wait-infra: install
	@poetry run python -m scripts.wait_infra

infra-down: prepare-env docker-check
	@$(COMPOSE) $(PROFILE) down

infra-ps: prepare-env docker-check
	@$(COMPOSE) $(PROFILE) ps

infra-logs: prepare-env docker-check
	@$(COMPOSE) logs -f postgres redis qdrant ollama

run: infra-up-gpu wait-infra
	@printf '\n%s\n' '------------------------------------------------------------'
	@printf '%s\n'   ' FASTAPI LOCAL - GPU'
	@printf '%s\n'   '------------------------------------------------------------'
	@printf '%s\n' 'Infra: Docker (PostgreSQL + Redis + Qdrant + Ollama)'
	@printf '%s\n' 'API:   processo Python local com auto-reload'
	@printf '%s\n\n' 'UI:    http://localhost:8001/ui'
	@GPU_TELEMETRY_ENABLED=true poetry run python -m scripts.run_local

run-cpu: infra-up wait-infra
	@printf '\n%s\n' '------------------------------------------------------------'
	@printf '%s\n'   ' FASTAPI LOCAL - CPU'
	@printf '%s\n'   '------------------------------------------------------------'
	@printf '%s\n\n' 'UI: http://localhost:8001/ui'
	@GPU_TELEMETRY_ENABLED=false poetry run python -m scripts.run_local

container-up: install docker-check
	@$(COMPOSE) $(PROFILE) up -d --build gateway
	@poetry run python -m scripts.wait_infra --gateway
	@printf '\nUI: http://localhost:8001/ui\n\n'

container-up-gpu: install gpu-check
	@$(COMPOSE_GPU) $(PROFILE) up -d --build gateway
	@poetry run python -m scripts.wait_infra --gateway
	@printf '\nUI: http://localhost:8001/ui\n\n'

container-rebuild: install gpu-check
	@$(COMPOSE_GPU) $(PROFILE) build --no-cache gateway
	@$(COMPOSE_GPU) $(PROFILE) up -d gateway
	@poetry run python -m scripts.wait_infra --gateway

# Backward-compatible aliases for the previous Makefile.
up: container-up
up-gpu: container-up-gpu

down: infra-down
ps: infra-ps
logs:
	@$(COMPOSE) $(PROFILE) logs -f gateway ollama qdrant postgres redis

models: prepare-env docker-check
	@$(COMPOSE) exec ollama ollama list

pull-model: prepare-env docker-check
	@test -n "$(MODEL)" || (echo 'Use: make pull-model MODEL=qwen3:4b' && exit 2)
	@$(COMPOSE) exec ollama ollama pull "$(MODEL)"

rm-model: prepare-env docker-check
	@test -n "$(MODEL)" || (echo 'Use: make rm-model MODEL=qwen3:4b' && exit 2)
	@$(COMPOSE) exec ollama ollama rm "$(MODEL)"

test:
	@poetry run pytest

lint:
	@poetry run ruff check .

import-check:
	@poetry run python -m scripts.import_check

check: lint test import-check
	@poetry run python -m compileall -q app scripts tests
	@printf '%s\n' 'compileall OK.'

smoke:
	@poetry run python -m scripts.smoke_openai

create-key:
	@poetry run python -m scripts.create_api_key --name "$(NAME)"

revoke-key:
	@test -n "$(KEY)" || (echo 'Use: make revoke-key KEY=sk-local-...' && exit 2)
	@poetry run python -m scripts.revoke_api_key --key "$(KEY)"

doctor: install docker-check
	@printf '\n%s\n' '--- NVIDIA ---'
	@if command -v nvidia-smi >/dev/null 2>&1; then nvidia-smi; else echo 'nvidia-smi indisponível'; fi
	@printf '\n%s\n' '--- CONTAINERS ---'
	@$(COMPOSE) $(PROFILE) ps
	@printf '\n%s\n' '--- INFRA ---'
	@poetry run python -m scripts.wait_infra --timeout 10
