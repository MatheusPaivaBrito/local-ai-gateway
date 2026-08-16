# Local AI Gateway

Gateway local **OpenAI-compatible** para desenvolvimento e testes com Ollama.
A arquitetura usa **DDD pragmático + Clean Architecture + vertical slices**, sem transformar o projeto em um conjunto de abstrações cerimoniais.

A versão `0.4.0` consolida o fluxo bare metal e adiciona catálogo remoto + progresso de download de modelos:

```text
FastAPI / Uvicorn       -> roda diretamente no WSL/Linux
PostgreSQL              -> Docker
Redis                   -> Docker
Qdrant                  -> Docker
Ollama                  -> Docker + GPU NVIDIA
```

Isso elimina rebuild do gateway a cada alteração de Python/HTML. O Uvicorn roda com `--reload`, então editar um arquivo local reinicia apenas o processo da API.

## Quick start recomendado

Primeira preparação da máquina/projeto:

```bash
make bootstrap
```

Depois, para desenvolver normalmente:

```bash
make run
```

Abra:

```text
UI:      http://localhost:8001/ui
Swagger: http://localhost:8001/docs
Qdrant:  http://localhost:6333/dashboard
Ollama:  http://localhost:11434
```

Para parar a infraestrutura:

```bash
make infra-down
```

## O que `make run` faz

`make run`:

1. cria `.env` a partir de `.env.example`, se necessário;
2. garante as dependências Python com Poetry;
3. valida Docker e acesso à GPU NVIDIA;
4. sobe PostgreSQL, Redis, Qdrant e Ollama no Docker;
5. aguarda os quatro serviços ficarem disponíveis;
6. inicia o FastAPI **fora do Docker** com auto-reload;
7. habilita a telemetria NVIDIA no processo local.

O Docker baixa automaticamente as imagens de infraestrutura ausentes na primeira subida. Nenhum modelo Ollama é baixado automaticamente.

## Bootstrap GPU

O bootstrap mostra o `nvidia-smi` completo e executa as verificações iniciais:

```bash
make bootstrap
```

Ele valida:

- NVIDIA / `nvidia-smi`;
- Docker;
- Docker Compose;
- acesso do Docker à GPU;
- `.env`;
- Poetry;
- lint, testes, import check e compileall;
- infraestrutura local.

O bootstrap **não mantém o FastAPI preso em container**. Ao final ele destaca os três modos de subida:

```bash
make run      # FastAPI local + infra Docker GPU, recomendado para desenvolvimento
make up       # projeto inteiro em containers, CPU
make up-gpu   # projeto inteiro em containers, GPU NVIDIA
```

No dia a dia, `make run` evita rebuild do gateway e mantém o Uvicorn com `--reload`.

## CPU

Para debug sem GPU/telemetria:

```bash
make run-cpu
```

Nesse modo o FastAPI continua local e o Ollama sobe sem o override de GPU.

## Modo totalmente containerizado

Continua disponível para smoke test de imagem ou ambiente mais próximo de deploy:

```bash
make container-up-gpu
```

CPU:

```bash
make container-up
```

Compatibilidade com os comandos antigos foi mantida:

```bash
make up-gpu
make up
```

Eles apontam para o modo totalmente containerizado.

Se quiser forçar um rebuild limpo do gateway:

```bash
make container-rebuild
```

O Dockerfile agora faz um **import smoke test durante o build**, portanto erro de módulo/slice faz o build falhar antes do Uvicorn iniciar.

---

# Arquitetura

```text
Cliente OpenAI / UI local
          |
          v
      FastAPI :8001
          |
  +-------+-----------+-------------+-------------+
  |                   |             |             |
  v                   v             v             v
Inference           Agents         RAG         API Keys
  |                   |             |             |
  |                   |             +--> Qdrant   +--> PostgreSQL
  |                   +--> PostgreSQL|
  |                        memória   +--> Ollama embeddings
  |
  +--> Ollama OpenAI-compatible API
  |
  +--> Usage + NVML telemetry --> PostgreSQL

Redis --> rate limit efêmero por API key
```

## Responsabilidade de cada serviço

| Serviço | Responsabilidade |
|---|---|
| FastAPI | API pública, composição dos domínios e UI local |
| Ollama | inferência, embeddings e catálogo de modelos instalados |
| PostgreSQL | API keys, agents, memória de threads e usage/telemetria |
| Redis | rate limiting efêmero |
| Qdrant | armazenamento e consulta vetorial para RAG |

O Redis **não é memória do agent**. A memória conversacional que precisa sobreviver a restart fica no PostgreSQL. Qdrant guarda contexto semântico, não histórico relacional de conversa.

## Estrutura

```text
app/
├── core/
│   ├── config.py
│   ├── database.py
│   ├── errors.py
│   └── security.py
├── domains/
│   ├── agents/
│   ├── api_keys/
│   ├── inference/
│   ├── model_catalog/
│   ├── rag/
│   ├── rate_limit/
│   └── usage/
├── http/
├── ui/
└── main.py

scripts/
├── create_api_key.py
├── import_check.py
├── revoke_api_key.py
├── run_local.py
├── smoke_openai.py
└── wait_infra.py
```

Cada pasta em `domains/` é uma vertical slice: rota, regra de aplicação, domínio e infraestrutura específica ficam próximas.

`app/main.py` é o composition root: instancia PostgreSQL, Redis, Ollama, Qdrant, telemetria e conecta os serviços.

---

# Correção do crash em `agents.repository`

O crash observado no gateway vinha de um detalhe real de Python na classe `AgentRepository`.

A classe possuía um método chamado:

```python
async def list(...)
```

E, mais abaixo no mesmo corpo de classe, havia uma annotation:

```python
-> list[AgentMessage]
```

Nesse ponto, `list` já podia resolver para o método da própria classe em vez do builtin, resultando em:

```text
TypeError: 'function' object is not subscriptable
```

A correção aplicada foi dupla:

- o método agora se chama `list_for_api_key`;
- `repository.py` usa `from __future__ import annotations`.

Além disso foram adicionados:

```bash
make import-check
```

E o `make check` agora inclui esse import check. O Dockerfile também importa explicitamente a slice de agents durante o build.

---

# Configuração local vs container

O `.env.example` agora é voltado ao fluxo recomendado, com o FastAPI local:

```dotenv
DATABASE_URL=postgresql+asyncpg://local_ai:local_ai_change_me@127.0.0.1:5432/local_ai
REDIS_URL=redis://127.0.0.1:6379/0
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_REGISTRY_BASE_URL=https://ollama.com
QDRANT_BASE_URL=http://127.0.0.1:6333
```

No modo containerizado, `compose.yaml` sobrescreve esses valores apenas dentro do container do gateway:

```text
postgres:5432
redis:6379
ollama:11434
qdrant:6333
```

Assim o mesmo projeto funciona nos dois modos sem manter dois arquivos `.env`.

As portas da infraestrutura são publicadas apenas em `127.0.0.1`.

---

# Modelos Ollama

Nenhum modelo de chat é fixado no Compose ou bootstrap.

A área **Modelos Ollama** tem agora dois catálogos distintos:

1. **catálogo remoto**: consulta a busca pública do `ollama.com` a partir do texto digitado e retorna modelos oficiais e da comunidade;
2. **catálogo local**: consulta `GET /api/tags` no Ollama local e mostra somente o que já está instalado.

A API local do Ollama documenta listagem dos modelos **instalados**, mas não um endpoint público de busca do registry. Por isso a vertical slice `model_catalog` trata `ollama.com/search` como catálogo HTML externo e mantém essa integração isolada em `infrastructure.py`.

Fluxo da UI:

```text
digitar "qwen"
      |
      v
GET /admin/models/registry/search?q=qwen
      |
      v
ollama.com/search
      |
      v
selecionar qwen3 / qwen3.8 / modelo da comunidade
      |
      v
ajustar tag se necessário, ex.: :4b
      |
      v
instalar
```

O download não é mais uma requisição opaca. O gateway mantém `stream=true` no `POST /api/pull`, repassa os eventos NDJSON ao browser e mostra:

- status atual do Ollama;
- bytes concluídos / total quando o Ollama informa esses campos;
- percentual da camada atual;
- tempo total decorrido;
- tempo desde o último evento, para ficar evidente se o download continua progredindo.

Endpoints administrativos:

```text
GET  /admin/models/registry/search?q=qwen
POST /admin/models/pull/stream
GET  /admin/models
```

Operações Ollama usadas por baixo:

```text
GET    /api/tags
POST   /api/pull       (stream=true para a UI)
DELETE /api/delete
```

Você ainda pode informar manualmente um nome/tag exato, por exemplo:

```text
qwen3:4b
```

ou instalar por terminal:

```bash
make pull-model MODEL=qwen3:4b
```

Listar:

```bash
make models
```

Remover:

```bash
make rm-model MODEL=qwen3:4b
```

Aliases públicos continuam opcionais:

```dotenv
MODEL_ALIASES={"gpt-5-nano":"qwen3:4b"}
```

Sem alias, use o nome Ollama diretamente na API.

Documentação oficial do Ollama:

- https://docs.ollama.com/api/tags
- https://docs.ollama.com/api/pull
- https://docs.ollama.com/api/streaming
- https://docs.ollama.com/api/openai-compatibility
- https://ollama.com/search

---

# Controle de thinking e output

Defaults:

```dotenv
INFERENCE_DEFAULT_MAX_OUTPUT_TOKENS=256
INFERENCE_DEFAULT_REASONING_EFFORT=none
```

Para Chat Completions, quando o cliente não define os campos, o gateway aplica:

```json
{
  "max_tokens": 256,
  "reasoning_effort": "none"
}
```

Isso evita que uma requisição trivial gaste centenas ou milhares de tokens de raciocínio por padrão.

Se o cliente enviar valores explicitamente, a escolha do cliente vence a policy default.

---

# RAG com Qdrant

Fluxo de ingestão:

```text
texto
  -> chunking
  -> Ollama /api/embed
  -> vetores
  -> Qdrant
```

Fluxo de busca:

```text
consulta
  -> embedding
  -> Qdrant top-k
  -> contexto recuperado
```

Modelo de embedding default:

```dotenv
RAG_EMBEDDING_MODEL=embeddinggemma
```

Ele também **não é instalado automaticamente**. Instale pela UI ou:

```bash
make pull-model MODEL=embeddinggemma
```

### Indexar documento

```http
POST /admin/rag/documents
Authorization: Bearer sk-local-...
Content-Type: application/json

{
  "collection": "manual_produto",
  "text": "conteúdo...",
  "metadata": {
    "source": "manual"
  }
}
```

### Buscar

```http
POST /admin/rag/search
Authorization: Bearer sk-local-...
Content-Type: application/json

{
  "collection": "manual_produto",
  "query": "como configurar?",
  "limit": 5
}
```

Qdrant local:

```text
http://localhost:6333/dashboard
```

---

# Agents e memória PostgreSQL

Um agent persiste:

- nome;
- system prompt;
- modelo;
- reasoning effort;
- limite de output;
- janela de memória;
- RAG opcional e collection associada.

A memória é separada por:

```text
api_key_id + agent_id + thread_id
```

Fluxo de chat com RAG:

```text
mensagem atual
   |
   +--> memória PostgreSQL
   |
   +--> busca Qdrant, se RAG ativo
   |
   v
system prompt + memória + contexto RAG + mensagem
   |
   v
Ollama
   |
   v
resposta
   |
   v
PostgreSQL
```

---

# Redis

O Redis tem uma responsabilidade pequena e explícita:

```text
rate limiting por API key / janela de tempo
```

O container está configurado sem persistência em disco porque esse estado pode ser perdido sem comprometer memória, agents ou usage.

---

# Comandos úteis

```bash
make help
make bootstrap
make run
make run-cpu
make infra-up-gpu
make infra-down
make infra-ps
make infra-logs
make doctor
make models
make pull-model MODEL=qwen3:4b
make rm-model MODEL=qwen3:4b
make check
make smoke
make create-key NAME=atlas-dev
```

## `make doctor`

Mostra:

- `nvidia-smi`;
- estado dos containers;
- conectividade de PostgreSQL;
- conectividade de Redis;
- Ollama;
- Qdrant.

---

# Validação

```bash
make check
```

Executa:

```text
Ruff
Pytest
Import check de todos os módulos app.*
compileall
```

O import check existe justamente para impedir que um erro de import de uma vertical slice sobreviva até a inicialização do Uvicorn.

---

# Fluxo de desenvolvimento sugerido

Uma vez:

```bash
make bootstrap
```

Todo dia:

```bash
make run
```

Edite qualquer arquivo Python/HTML normalmente. Não há rebuild do FastAPI.

Quando terminar:

```bash
Ctrl+C
make infra-down
```

Se quiser testar a imagem Docker do gateway antes de fechar uma alteração:

```bash
make container-up-gpu
```
