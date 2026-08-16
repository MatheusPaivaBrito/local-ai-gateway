# Review / v0.4.0

## Objetivo desta revisão

A versão 0.4.0 mantém a arquitetura DDD pragmática / Clean Architecture / vertical slices da 0.3.0 e melhora especificamente o domínio `model_catalog` e a ergonomia de execução.

## Catálogo remoto do Ollama

O Ollama documenta `GET /api/tags` para modelos já presentes no host local, mas não documenta um endpoint local de busca do registry público.

Foi criado `OllamaRegistryClient`, isolado em `app/domains/model_catalog/infrastructure.py`, que consulta a página pública `ollama.com/search?q=...` e converte os resultados em `RegistryModel`.

A UI usa:

```text
GET /admin/models/registry/search?q=<texto>
```

O campo de busca é debounced; os resultados entram em um select e a escolha preenche o nome/tag a ser instalado. O campo final continua editável para permitir variantes como `:4b`, `:8b` etc.

A integração HTML é deliberadamente isolada porque o markup do site público é um contrato menos estável que a API local do Ollama.

## Download com progresso

A versão anterior usava `stream=false` no pull e a UI só sabia que "estava baixando".

Agora existe:

```text
POST /admin/models/pull/stream
```

O backend chama `POST /api/pull` com `stream=true`, consome os eventos NDJSON do Ollama e os repassa ao browser também como NDJSON.

A UI mostra:

- status corrente;
- `completed / total` quando disponível;
- percentual da camada atual;
- tempo decorrido;
- segundos desde o último evento recebido.

Isso torna travamentos aparentes sem polling artificial do download.

## Bootstrap / modos de execução

O final do `make bootstrap` agora destaca explicitamente:

```bash
make run      # FastAPI local + infraestrutura Docker/GPU
make up       # tudo em containers / CPU
make up-gpu   # tudo em containers / GPU NVIDIA
```

`make run` segue como o fluxo de desenvolvimento recomendado porque mantém `uvicorn --reload` fora do container e elimina rebuild do gateway a cada alteração.

## Validação desta revisão

Executado no artefato final:

```text
pytest: 22 passed
compileall: OK
JavaScript syntax (node --check): OK
Makefile parse: OK
```

Também foram adicionados testes para:

- parsing de modelos oficiais e de comunidade na busca do registry;
- delegação da busca remota pelo `ModelCatalogService`;
- propagação dos eventos de progresso do pull.
