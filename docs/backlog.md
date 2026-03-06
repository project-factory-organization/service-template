# Backlog

## Spec-First API Generation — Future Improvements

### Spec-First Async Messaging (Queues)

**Status**: DONE

**Description**: Support asynchronous messaging via queues.
- **Decision**: We chose **Redis** (Streams) + **FastStream**.
    - **Why**: Fits "Rigidity is Freedom". Single container, strongly typed, spec-first.
- **Goal**: Define topics/events in YAML.
- **Generation**: Auto-generate consumers and producer wrappers using FastStream.
- **Validation**: Ensure messages conform to schemas defined in `models.yaml`.

> **Реализовано:** `EventsGenerator`, `EventAdapterGenerator` генерируют pub/sub код из `events.yaml`. Lazy broker через `get_broker()`. Полностью spec-driven.

### Spec-Only Module Storage (Long-term Vision)

**Status**: IDEA
**Priority**: LOW (Long-term architectural evolution)

**Description**: Store only specs and minimal scaffolds for template modules instead of full implementation code. Generate all business logic on project creation.

**Current State**:
- Template stores complete implementation: controllers, models, repositories, etc.
- Modules (backend, tg_bot, etc.) are selected via Jinja conditions during `copier copy`
- Creates distinction between "built-in batteries" and user-added services

**Proposed State**:
- Template stores only:
  - Domain specs (`services/backend/spec/*.yaml`)
  - Infrastructure scaffolds (`src/core/`, `scripts/`, minimal `pyproject.toml`)
- Delete implementation code: controllers, models, repositories
- On `copier copy`, automatically run `make setup` (which includes `make generate-from-spec`)

**Benefits**:
- ✅ Perfect spec-first implementation (no code drift from specs)
- ✅ Massive token economy win (only specs to read/edit)
- ✅ Zero distinction between built-in and custom services
- ✅ Simpler compose management (no markers needed, full generation)
- ✅ Cleaner framework updates via `copier update`

**Challenges**:
- ❌ Controllers contain business logic hard to specify generically
- ❌ ORM models need DB-specific types, indexes, relationships
- ❌ No reference implementation in template (harder to debug framework)
- ❌ Bootstrap requires generation step (slower initial copy)
- ❌ Generators must handle validation rules, hooks, complex logic

**Prerequisites for Implementation**:
1. Create ORM model generator from extended specs
2. Add validation/constraint rules to operation specs
3. Implement convention-based controller hooks/stubs
4. Enhance scaffolding templates for business logic slots
5. Add reference implementation outside template for framework development

**Recommended Path**:
1. **Short-term**: Current hybrid approach (Jinja templates)
2. **Medium-term**: Keep specs + minimal scaffolds, delete business logic
3. **Long-term**: Pure spec-only after generator maturity (2-3 months)

### Celery Worker Support

**Status**: IDEA

**Description**: Add native support for distributed tasks via Celery.
- **Spec**: Allow defining a service type as `celery-worker` in `services.yml` or `AGENTS.md`.
- **Integration**: Pre-configured Redis/RabbitMQ in docker-compose.
- **Scaffolding**: Generate `celery_app` instance and task decorators automatically.

### High-Level Architecture Spec ("Who talks to whom")

**Status**: IDEA

**Description**: Introduce a centralized "Connectivity Graph" specification.
- **Problem**: Currently, dependencies (DB access, inter-service calls) are implicit in code.
- **Solution**: Explicitly define service relationships in `services.yml` or a new `architecture.yaml`.
    - `access: [database, internet]`
    - `exposes: [rest, rpc]`
    - `consumes: [auth-service.v1.verify_token]`
- **Outcome**: Generate explicit typed clients ("SDKs") for internal services and firewall rules/network policies in Docker Compose.

### Auto-fuzzing and Contract Testing

**Status**: IDEA

**Description**: Integrate contract testing tools like `schemathesis` into the CI pipeline.
- **Mechanism**: The tool reads the generated `openapi.json` and fuzzes the running service with valid and invalid inputs.
- **Goal**: Automatically detect 500 errors and edge case failures without writing manual tests. If the code doesn't handle inputs described in the spec, the build fails.

### Spec-First Observability

**Status**: IDEA

**Description**: Automatically embed OpenTelemetry traces and metrics into generated code.
- **Mechanism**: Wrap generated router endpoints with telemetry decorators.
- **Goal**: Zero-config observability. Defining an endpoint `POST /users` in the spec automatically yields metrics like `http_requests_total{route="/users"}` and traces with propagated Request-IDs.

## Distribution & Usage Evolution

### 1.1 Add Predefined Module to Existing Project

**Status**: TODO

**Description**: Allow adding a predefined module (tg_bot, notifications, frontend) to an existing project that was initially generated without it.

- **Problem**: Copier's `update` command updates infrastructure but cannot add modules that were excluded during initial generation. The `_tasks` in `copier.yml` delete unselected module directories, making them unavailable for later addition.

- **Use Case**: Agent generates project with `modules=backend`, later decides to add `tg_bot`.

- **Current Workaround**: Re-generate project with all desired modules (loses customizations) or manually copy module from template.

- **Proposed Solution**: `make add-module name=tg_bot` command that:
  1. Validates module is in predefined list (backend, tg_bot, notifications, frontend)
  2. Fetches module directory from template repository (via git archive or copier partial)
  3. Updates `services.yml` to include the new module
  4. Runs `make setup` to install deps and regenerate
  5. Updates `.copier-answers.yml` to reflect new module selection

- **Considerations**:
  - How to handle template version mismatch (project on v1.0, template on v2.0)?
  - Should module addition trigger compose regeneration automatically?
  - Integration with `copier update` — should it respect manually added modules?

### 2. CLI Wrappers

**Status**: IDEA

**Description**: Wrap `make` commands and boilerplate scripts into a standalone CLI tool (distributed via PyPI or binary).
- **Why**: Simplify usage for both humans and agents.
- **Commands**:
    - `my-framework init` (wraps `copier copy`)
    - `my-framework sync` (wraps `make setup`)
    - `my-framework update` (wraps `copier update`)

### 4. Context Packer

**Status**: IDEA

**Description**: A tool to optimize context loading for agents.
- **Problem**: Agents waste tokens reading unrelated files.
- **Solution**: A command like `make context service=backend` that aggregates:
    - Relevant Spec (models + paths)
    - `AGENTS.md` for the service
    - Signatures of imported modules
    - Current linter errors
- **Goal**: Provide a single, token-optimized file containing strictly necessary information for the current task.

---

## Integration Test Compose Bugs

### Host venv shebang incompatible with container runtime

**Status**: DONE
**Priority**: CRITICAL

**Description**: `compose.tests.integration.yml.jinja` used `PATH: /workspace/services/backend/.venv/bin:...`. In CI, host-built `.venv` shebangs pointed to host Python — broke container runtime.

**Fix applied**: PATH changed to `/app/services/backend/.venv/bin:...` (image venv) + anonymous volume `- /app/services/backend/.venv` to shadow host venv. Copier tests in `TestIntegrationCompose` verify PATH doesn't reference `/workspace/.venv`.

### No backend readiness check in integration compose

**Status**: DONE
**Priority**: CRITICAL

**Description**: `compose.tests.integration.yml.jinja` used `depends_on: condition: service_started` — integration tests raced against backend startup.

**Fix applied**: Added healthcheck (python urllib to `/health`, interval 2s, retries 15, start_period 5s) + switched to `condition: service_healthy`. Copier tests in `TestIntegrationCompose` verify healthcheck presence and `service_healthy` condition.

---

## Compose / Deploy Bugs

### compose.base.yml: `${VAR:?}` breaks env_file-based workflows

**Status**: DONE
**Priority**: CRITICAL

**Description**: `x-backend-env` anchor in `compose.base.yml` used `${POSTGRES_USER:?}` (required-or-fail syntax). Docker Compose evaluates these from the **shell environment** before processing `env_file` directives — broke any compose command unless vars were pre-exported.

**Fix applied**: Replaced `${VAR:?}` with `${VAR}` in `x-backend-env` anchor. Validation of required vars is handled by the app's `Settings` class at startup. Copier test `test_base_compose_no_required_var_syntax` prevents regression.

### deploy.yml does not verify container health after deploy

**Status**: DONE
**Priority**: CRITICAL

**Description**: `deploy.yml.jinja` ran `docker compose up -d` and reported success immediately. If the container crashed on startup, the deploy workflow still completed green.

**Fix applied**: Post-deploy health check added — `sleep 15` + `$COMPOSE ps --format json` + python script that checks container State and calls `sys.exit(1)` on failure. Copier tests `test_deploy_verifies_container_health` and `test_deploy_script_fails_fast` prevent regression.

### Убрать `.env.prod` — на проде нужен только один `.env`

**Status**: DONE
**Priority**: HIGH

**Description**: `compose.prod.yml` ссылается на два env-файла: `../.env` (основной) и `./.env.prod` (production overrides). На практике `.env.prod` **всегда пустой** — все переменные (infra, computed, user) уже собираются оркестратором в один `DOTENV_B64` и декодируются в `.env` при деплое. `.env.prod` только `touch`-ится чтобы compose не падал с "file not found".

**Почему это проблема**:

1. **Ломает деплой при любом сбое в цепочке**. Если `touch` не выполнился (например, ошибка в deploy.yml или изменение порядка шагов) — весь compose падает. Это уже случалось в production E2E тестах (BUG 8 из `e2e-reverse-echo-bot-deploy-failure`).
2. **Вводит в заблуждение**. Два env-файла создают впечатление что есть разделение "base vs prod overrides", но оркестратор этого разделения не поддерживает — он собирает единый набор переменных. Агент, читающий compose, может ошибочно решить что нужно что-то писать в `.env.prod`.
3. **Лишняя точка отказа без пользы**. На сервере всё и так production — нет сценария где `.env` содержит dev-значения а `.env.prod` их перекрывает.

**Что сделать**:

1. `compose.prod.yml.jinja` — убрать `- ./.env.prod` из всех `env_file` директив
2. `deploy.yml.jinja` — убрать `touch "$PROJECT_DIR/infra/.env.prod"`
3. Удалить `infra/.env.prod.jinja` из шаблона
4. `deploy.yml.jinja` — добавить fail-fast проверку после decode `.env`:
   ```bash
   printf '%s' "$DOTENV_B64" | base64 -d > "$PROJECT_DIR/.env"
   if [ ! -s "$PROJECT_DIR/.env" ]; then
     echo "FATAL: decoded .env is empty — DOTENV secret missing or corrupt"
     exit 1
   fi
   ```

**Обратная совместимость**: Для уже задеплоенных проектов `.env.prod` остаётся на сервере как пустой файл — это безвредно, compose просто перестанет на него ссылаться. Нужен re-scaffold или manual patch compose-файлов.

---

## Template / Copier Issues

### ~~Copier tests (`tests/copier/`) нужно переписать~~ → ✅ Done

**Status**: DONE

Переписаны в коммите `44a17d8`. 68 быстрых + 5 медленных тестов. Fixture обновлён, тесты включены в pre-push hook.

### Enum Types in Model Fields

**Status**: IDEA

**Description**: Add support for enum types in model field definitions.

**Example**:
```yaml
models:
  Book:
    fields:
      status:
        type: enum
        values: [wishlist, reading, finished]
        default: wishlist
```

**Benefit**: Generated Pydantic models would use `Literal` or `Enum` types instead of plain strings.

---

## Usability Issues (from Testing Feedback)

### tg_bot AGENTS.md documents wrong env var name

**Status**: DONE
**Priority**: MEDIUM
**Источник**: E2E weather_bot Level C (2026-03-04), codegen_orchestrator

**Description**: `template/services/tg_bot/AGENTS.md.jinja:40` documents `API_BASE_URL` but the actual code (`main.py.jinja:49`) and `.env.jinja:22` use `BACKEND_API_URL`. Agent reads AGENTS.md, writes code using the wrong variable name, may get runtime errors.

**Root cause**: Commit `370b297` (2026-02-09) renamed the variable in `.env`, `.env.example`, and `main.py` but missed `AGENTS.md.jinja`. Inconsistency persisted for 3+ weeks.

**Fix**: One-line change in `template/services/tg_bot/AGENTS.md.jinja:40` — replace `API_BASE_URL` with `BACKEND_API_URL`.

### Добавить примеры роутеров и list-эндпоинтов в AGENTS.md

**Status**: DONE
**Priority**: MEDIUM

**Description**: AGENTS.md не содержит примера роутера и list-эндпоинта. После удаления `RoutersGenerator` (см. `docs/simplification-plan.md`) агент пишет роутеры вручную, но в документации нет ни одного примера — как выглядит роутер, как подключить его в `router.py`, как объявить list-операцию в спеке.

**Контекст**: В E2E тесте `todo_api` (2026-03-02) developer-воркер потратил время на поиск паттернов в исходниках:
- Пробовал `response_list: true` в спеке → ошибка валидации. Правильный синтаксис `output: list[TodoRead]` нашёл только в коде фреймворка.
- Роутер и подключение в `router.py` писал без образца, ориентируясь на существующий `users` домен.

**Что добавить в AGENTS.md**:
1. Пример domain YAML с list-операцией (`output: list[Model]`)
2. Пример роутера (15-20 строк: FastAPI router, dependency injection контроллера через protocol, session)
3. Пример подключения роутера в `app/api/router.py`
4. Упоминание PATCH как альтернативы PUT для partial updates

### Codegen quality: косметические баги в generated output

**Status**: DONE
**Priority**: LOW
**Источник**: Worker audit report, E2E todo_api Level C (2026-03-02)

Три мелких бага в кодогенерации, которые не ломают функциональность, но создают шум и путают разработчиков/агентов.

**Подзадачи** (все закрыты):

1. **Update schema defaults: `""` / `False` вместо `None`** — DONE. `_model_to_schema()` теперь удаляет оригинальный `default` для variant-optional полей (`prop.pop("default", None)`).

2. **Inconsistent indentation в generated protocols** — DONE. Корень: `lstrip_blocks=False` в `ProtocolsGenerator` (единственный генератор с таким значением). Плюс `format_file()` вызывал голый `ruff` без пути к venv → `FileNotFoundError` → тихий `pass`. Фиксы: (a) `lstrip_blocks=True`, (b) `format_file()` теперь использует `.venv/bin/ruff` по абсолютному пути.

3. **Trailing whitespace в scaffolded `lifespan.py`** — DONE. `{% endif -%}` на последнем тэге убирает trailing blank line.

### Codegen quality: param types и optional schemas

**Status**: DONE
**Priority**: HIGH / LOW
**Источник**: E2E todo_api Level C (2026-03-03), worker audit report

Два бага:

1. **UUID param type: `uuid` (модуль) вместо `UUID` (класс)** — DONE. `ParamSpec.type` (plain `str`) передавался в шаблоны протоколов/контроллеров без конвертации через `type_spec_to_python()`. Фикс: `OperationContextBuilder._build_params()` теперь конвертирует типы и собирает `param_type_imports` (`from uuid import UUID`, `from pydantic import AwareDatetime`). Шаблоны `protocols.py.j2` и `controller.py.j2` рендерят эти импорты.

2. **Optional + non-None default: `str | None = ""`** — DONE. `FieldSpec.to_json_schema()` безусловно ставил `nullable: true` при `optional: true`. Фикс: nullable добавляется только когда `default is None`.

### Add E2E CI Job for Unified Handlers

**Status**: DONE
**Priority**: MEDIUM

**Description**: `test_e2e_dual_transport_pipeline` в `TestSlowIntegration` — генерирует проект с `backend,tg_bot` (dual-transport: REST + events), запускает полный pipeline: `make setup` → `make generate-from-spec` (idempotency) → `make lint` → `make tests`. Запускается через `make test-copier-slow` и в CI (`test-template.yml` → `test-pytest` job).

### Нет list-операции в reference User домене

**Status**: DONE
**Priority**: MEDIUM

**Description**: User domain (reference implementation) не содержал `list_users` — базовую CRUD-операцию. E2E воркер нашёл пример list-эндпоинта только в AGENTS.md, но не в работающем коде.

**Фикс**: Добавлены `list_users` operation в `users.yaml`, метод `list()` в `UserRepository`, `list_users()` в controller, GET `/users` endpoint в router, тест. Протокол регенерирован.

### Пояснение про shared/shared/ структуру

**Status**: DONE
**Priority**: LOW

**Description**: Двойная вложенность `shared/shared/` путала агентов. Это стандартная Python packaging convention (project root vs importable package). Добавлено пояснение в AGENTS.md.

---

### compose.dev.yml: PATH не включает per-service .venv

**Status**: DONE

**Description**: В `infra/compose.dev.yml.jinja` добавлен `PATH` с per-service `.venv/bin` + стандартный системный PATH из `python:X-slim` для всех трёх сервисов (backend, tg_bot, notifications_worker). Hardcoded PATH вместо `${PATH}` (утечка хостовых путей) или `$$PATH` (не раскрывается).

---

## Jinja Whitespace в шаблонах документации

**Status**: DONE
**Priority**: LOW

**Description**: Шаблоны `TASK.md.jinja`, `CONTRIBUTING.md.jinja`, `ARCHITECTURE.md.jinja` генерировали лишние пустые строки. Проверка показала — лишних пустых строк больше нет.

---

## CI / Deploy Pipeline Bugs

### Generated code не попадает в Docker-образ → backend crash loop на deploy

**Status**: DONE
**Priority**: CRITICAL

**Description**: При деплое backend-контейнер падает с `ModuleNotFoundError: No module named 'shared.generated'`. Проблема воспроизведена в двух последовательных E2E тестах Level C (todo_api, 2026-03-02) — оба раза одинаковый crash loop.

**Ошибка на сервере**:
```
File "/app/services/backend/src/app/schemas/__init__.py", line 3, in <module>
    from shared.generated.schemas import (
ModuleNotFoundError: No module named 'shared.generated'
```

**Цепочка**: `start.sh` → `alembic upgrade` → `env.py` → models → `app/__init__.py` → router → routers → controllers → repositories → `schemas/__init__.py` → `from shared.generated.schemas import ...` → **crash**.

**Корневая причина** — два бага, которые вместе дают проблему:

1. **`.gitignore` исключает generated-код.** `template/.gitignore` строка 19: `**/generated/`. Scaffold запускает `make setup` → `make generate-from-spec`, создаётся `shared/shared/generated/schemas.py`, но `git add .` пропускает эти файлы. Generated-код никогда не попадает в GitHub.

2. **CI job `build-and-push` не регенерирует файлы.** В `ci.yml.jinja` job `lint-and-test` запускает `make generate-from-spec` (строка ~42), но это отдельный job — его workspace не переносится. Job `build-and-push` делает только `actions/checkout@v4` + Docker build из чистого checkout без generated-файлов. `Dockerfile.jinja` строки 26, 33 (`COPY shared/shared` / `COPY shared`) копируют то что есть в build context — а `shared/shared/generated/` там нет.

**Почему CI тесты проходят, а deploy падает**: `lint-and-test` регенерирует файлы в своём workspace и запускает тесты вне Docker. Тесты проходят. Затем `build-and-push` собирает Docker-образ из чистого checkout → образ без `shared/shared/generated/` → backend crash при старте.

**Затронутые файлы**:
- `template/.gitignore:19` — правило `**/generated/`
- `template/.github/workflows/ci.yml.jinja:~42` — генерация только в `lint-and-test`
- `template/.github/workflows/ci.yml.jinja:~94-95` — `build-and-push` без генерации
- `template/services/backend/Dockerfile.jinja:26,33` — COPY предполагает наличие generated-файлов

**Рекомендации по решению** (в порядке предпочтения):

| Вариант | Что сделать | Трейдофф |
|---------|-------------|----------|
| A. Генерить в `build-and-push` | Добавить step `make generate-from-spec` перед Docker build в `ci.yml.jinja` | Нужен `datamodel-code-generator` в CI runner (pip install) |
| B. Трекать generated в git | Убрать `**/generated/` из `.gitignore` | Generated-код в git, зато всегда доступен |
| C. Генерить в Dockerfile | Добавить `RUN make generate-from-spec` в `Dockerfile.jinja` | Dev-зависимость в prod-образе, медленнее билд |

**Воспроизведение**: Создать проект с `modules: [backend]`, пройти scaffold → codegen → CI → deploy. Backend упадёт при старте.

**Ссылки**: `codegen_orchestrator/docs/e2e_results/todo_api-20260302-levelC.md`, `todo_api-20260302-levelC-2.md`

---

### CI: добавить `deptry` для обнаружения отсутствующих runtime-зависимостей

**Status**: DONE
**Priority**: HIGH

**Description**: Coding agent добавил `import httpx` в runtime-код (`lesswrong.py`), но `httpx` был только в `[dependency-groups] dev`. CI тесты прошли (dev-deps установлены), Docker-образ собрался, но backend падает на проде с `ModuleNotFoundError: No module named 'httpx'`. Классическая ошибка "works in dev, crashes in prod".

**Решение**: Добавить [`deptry`](https://github.com/fpgmaas/deptry) в CI pipeline (`ci.yml.jinja`). `deptry` статически анализирует импорты и сравнивает с `pyproject.toml` — находит:
- **DEP002**: пакет в dev-deps, но импортируется в runtime-коде (наш случай)
- **DEP001**: импорт пакета, которого нет в dependencies вообще
- **DEP003**: transitive dependency used directly

**Затронутые файлы**:
- `template/.github/workflows/ci.yml.jinja` — добавить step `uv run deptry .` в `lint-and-test` job
- `template/services/backend/pyproject.toml.jinja` — добавить `deptry` в dev-deps
- Аналогично для `tg_bot` если есть `pyproject.toml`

**Источник**: fortune-telling-bot deploy failure 2026-03-07 (`codegen_orchestrator`)

---

## Infrastructure Audit Fixes

### Add Cache Mounts to Dockerfiles

**Status**: DONE

**Description**: `--mount=type=cache,target=/root/.cache/uv` добавлен в Dockerfile.jinja для backend, tg_bot, notifications_worker.

### Audit Scaffold Templates

**Status**: TODO
**Priority**: LOW

**Description**: Review templates in `.framework/framework/templates/scaffold/services/` to ensure they use the latest best practices adopted by main services.

## Simplification & Unification Tasks

### Unified Handlers: Error Handling Strategy

**Status**: TODO
**Priority**: MEDIUM

**Description**: Formulate a strategy for handling errors in event handlers. Should we use Dead Letter Queues (DLQ), publish an error event (`events.publish_on_error`), or implement retries with exponential backoff?

### Unified Handlers: Transactional Outbox Pattern

**Status**: IDEA
**Priority**: LOW

**Description**: Currently, events are published directly after DB writes. Consider implementing the Transactional Outbox pattern to avoid the dual write problem and ensure reliable event publishing.

---

## Rust Migration Preparation

> **Контекст**: см. `docs/rust-migration-analysis.md` — анализ перспективы переписывания шаблона на Rust для более строгого feedback loop при agent-driven разработке.

### Сделать YAML-спеки language-agnostic

**Status**: PARTIALLY DONE
**Priority**: LOW

**Description**: Спеки уже используют абстрактные типы (`int`, `string`, `bool`, `float`, `datetime`, `uuid`) — не Python-специфичные. Коллекции: `list[T]`, `dict[K,V]` — shorthand-нотация, парсится `TypeSpec` (discriminated union в `framework/spec/types.py`). Маппинг централизован (см. пункт выше).

**Осталось**: shorthand `list[string]` всё ещё Python-подобный. Рассмотреть переход на JSON Schema `array` + `items` для полной language-agnosticity. Низкий приоритет — текущий формат работает для Python и TypeScript.

### Rust PoC: backend сервис на Axum

**Status**: IDEA
**Priority**: LOW

**Description**: Написать Proof of Concept — аналог `services/backend/` на Rust (Axum + SeaORM 2.0 + utoipa). Тот же API, тот же Docker, тот же compose. Цель — проверить, насколько AI-агент справляется с генерацией Axum-кода и насколько spec-first подход переносим.

**Стек**: Axum 0.8+, SeaORM 2.0, utoipa, reqwest, tokio.

### Rust PoC: Telegram bot на teloxide

**Status**: IDEA
**Priority**: LOW

**Description**: Написать PoC Telegram-бота на teloxide как альтернативу `services/tg_bot/`. Teloxide (3.4k stars) — зрелый фреймворк с compile-time типизацией команд. Сравнить developer experience и agent experience с текущим python-telegram-bot.

### Вынести маппинг типов из генераторов

**Status**: PARTIALLY DONE
**Priority**: LOW

**Description**: Маппинг уже централизован в `framework/spec/types.py` — функции `type_spec_to_python()`, `type_spec_to_json_schema()`. Отдельные маппинги в `framework/frontend/generator.py` (TypeScript) и `framework/openapi/generator.py` (OpenAPI). Осталось: (1) унифицировать все маппинги через единую таблицу/конфиг, (2) вынести в YAML/TOML для добавления новых языков без кода.

### Исследовать Tera как замену Jinja2 для codegen

**Status**: IDEA
**Priority**: LOW

**Description**: Tera — Rust-аналог Jinja2 с почти идентичным синтаксисом. Оценить, насколько текущие шаблоны из `framework/templates/codegen/` могут быть переиспользованы в Tera с минимальными изменениями. Если синтаксис совместим на 90%+, это снизит стоимость миграции codegen pipeline.

### Добавить Rust service type в services.yml

**Status**: IDEA
**Priority**: LOW

**Description**: Расширить список типов сервисов в `services.yml` типом `rust-axum`. Добавить scaffold-шаблон в `.framework/framework/templates/scaffold/services/rust-axum/` с базовым Cargo.toml, Dockerfile (multi-stage с cargo-chef), и main.rs. Это позволит смешивать Python и Rust сервисы в одном проекте — естественный путь постепенной миграции.

---

## Dev Environment (orchestrator integration)

### compose.dev.yml: `ports:` ломает worker-контейнеры orchestrator'а

**Status**: OPEN
**Priority**: CRITICAL
**Источник**: E2E diagnostic run codegen_orchestrator (2026-03-07), подтверждено live user run

**Description**: `infra/compose.dev.yml.jinja` публикует `ports: - "5432:5432"` для db и `ports: - "6379:6379"` для redis. Когда проект запускается внутри worker-контейнера orchestrator'а, на хосте уже работает orchestrator'ский postgres на порту 5432. Результат: `docker compose up db` падает с `Bind for 0.0.0.0:5432 failed: port is already allocated`, контейнер db не стартует, DNS alias `db` не регистрируется, `getent hosts db` возвращает пустоту, alembic падает с `failed to resolve host 'db'`.

**Почему это корневая причина "рекурсивного бага миграций"**: В codegen_orchestrator этот баг чинили 10 раз (коммиты `6530d68`..`3138d87`, февраль-март 2026). Все фиксы были направлены на DNS/network isolation, но реальная причина — ports конфликт. Баг "то есть, то нет" потому что зависит от того, занят ли порт 5432 на хосте.

**Диагностика** (из DIAGNOSTIC_REPORT.md worker'а):
```
Step 4: orchestrator dev-env start-infra db
  Error: Bind for 0.0.0.0:5432 failed: port is already allocated
Step 5: getent hosts db
  (no output - exit code 2, hostname 'db' does not resolve)
Step 6: getent hosts redis
  172.19.0.2 redis   <-- резолвится, потому что это orchestrator'ский redis
Step 11: make migrate
  psycopg.OperationalError: failed to resolve host 'db'
```

**Решение**: Ports нужны для локальной разработки без orchestrator'а — шаблон не трогаем. Фикс на стороне orchestrator'а: compose_runner инжектит override с `ports: []`. См. `codegen_orchestrator/docs/backlog.md` задача #53.

**Затронутые файлы** (контекст для разработчика):
- `template/infra/compose.dev.yml.jinja:58-59` — `ports: - "5432:5432"` для db
- `template/infra/compose.dev.yml.jinja:67-68` — `ports: - "6379:6379"` для redis

---

### Makefile: `makemigrations` не загружает `.env`

**Status**: DONE
**Priority**: HIGH
**Источник**: E2E тесты codegen_orchestrator (todo_api Level A/B/C, 2026-03-02), воспроизводится стабильно.

**Description**: `make makemigrations name="..."` запускает Alembic напрямую в shell без загрузки переменных окружения из `.env`. Alembic импортирует `settings.py` → `get_settings()` → `_validate_required_env_vars()` → `RuntimeError: Required environment variables are not set: APP_NAME, APP_ENV, APP_SECRET_KEY, POSTGRES_HOST, ...`.

Агент (Claude Code в worker-контейнере) вызывает `orchestrator dev-env start-infra db` — PostgreSQL поднимается. Но `make makemigrations` падает, потому что в shell нет env vars. Агент вынужден писать миграции вручную.

**Текущий таргет в Makefile**:
```makefile
makemigrations:
	PYTHONPATH=. services/backend/.venv/bin/alembic -c services/backend/migrations/alembic.ini revision --autogenerate -m "$(name)"
```

**Фикс**: Добавить `include .env` в начало Makefile (или как минимум `source .env` в таргете makemigrations). Аналогично для таргетов `migrate` и `test-integration`, которые тоже нуждаются в DB-коннекте.

```makefile
# В начале Makefile:
-include .env
export
```

Минус `-include` (с дефисом): если `.env` нет — тихо пропускает. `export` прокидывает все переменные в subprocess.

**Проверка**: После фикса в шаблоне, в сгенерированном проекте `make makemigrations name="test"` должен работать без предварительного `source .env`.

### Makefile: нет `make migrate` таргета → autogenerate невозможен

**Status**: DONE
**Priority**: HIGH
**Источник**: E2E codegen_orchestrator todo_api Level C (2026-03-03), воспроизведено вручную.

**Description**: Scaffold создаёт начальные миграции (`0001_initial`, `create_user`), но в Makefile нет таргета для их применения (`alembic upgrade head`). Когда воркер-агент:

1. Запускает `orchestrator dev-env start-infra db` — postgres стартует, `.env` патчится (`POSTGRES_HOST=project-db`)
2. Пробует `make makemigrations name="add_todo"` — Alembic подключается к БД успешно, но падает с `Target database is not up to date` (начальные миграции не применены)
3. Ищет `make migrate` — не существует
4. Пробует `alembic upgrade head` напрямую (без make) — env vars не загружены → `RuntimeError: Required environment variables are not set`
5. Сдаётся и пишет миграцию вручную

**Воспроизведено**: В worker-контейнере после scaffold: `orchestrator dev-env start-infra db` → OK, `make makemigrations name='test'` → "Target database is not up to date", `source .env && alembic upgrade head` → OK, `make makemigrations name='test'` → OK. Вся цепочка работает, но без `make migrate` агент не может к ней прийти.

**Фикс**: Добавить таргет `migrate` в `template/Makefile.jinja`:

```makefile
migrate:
	PYTHONPATH=. services/backend/.venv/bin/alembic -c services/backend/migrations/alembic.ini upgrade head
```

Аналогично `makemigrations`, env vars подхватятся через `-include .env` + `export` в начале Makefile.

**Опционально**: Обновить `AGENTS.md` — добавить пример workflow: `make migrate` → `make makemigrations name="..."` → `make migrate`.

### Broken import in scaffolded user repository

**Status**: DONE
**Priority**: HIGH
**Источник**: E2E codegen_orchestrator todo_api with-PO (2026-03-05)

**Description**: `services/backend/src/app/repositories/user.py:9` imports `from ..schemas import UserCreate, UserUpdate` but the schemas module doesn't exist at that path — schemas are generated in `shared/shared/generated/schemas.py`. Causes `ModuleNotFoundError` and blocks `make migrate`, `make tests`, and any backend import. Fix: update scaffold template to generate `from shared.generated.schemas import UserCreate, UserUpdate` or add re-export module at `services/backend/src/app/schemas.py`.

### Eager import chains cause fragility in scaffolded projects

**Status**: OPEN
**Priority**: LOW
**Источник**: E2E codegen_orchestrator todo_api with-PO (2026-03-05)

**Description**: `services/backend/src/__init__.py` eagerly imports `app` and `create_app`, and `api/__init__.py` eagerly imports the router. Any broken import in the chain (routers → controllers → repositories → schemas) causes the entire application to fail at import time. Alembic migrations also affected since `env.py` triggers full app initialization. Fix: use lazy imports or have Alembic `env.py` import models directly without app initialization chain.

### ORMBase forces `updated_at` on all models

**Status**: DONE
**Priority**: LOW
**Источник**: E2E codegen_orchestrator todo_api Level C (2026-03-04)

**Description**: `ORMBase` bundles both `created_at` and `updated_at` columns. Models that only need `created_at` (e.g., Todo per spec) must use `Base` directly and define `created_at` manually, losing `ORMBase` convenience.

**Fix applied**: `CreatedAtMixin` добавлен в `db.py` (коммит `b0afb10`). Модели могут наследовать `CreatedAtMixin` + `Base` для `created_at` only, или `ORMBase` для обоих timestamps.

### Auto-generate routers from domain specs

**Status**: OPEN
**Priority**: MEDIUM
**Источник**: E2E codegen_orchestrator todo_api Level C (2026-03-04)

**Description**: Framework generates protocols and controller stubs from specs, but routers must be written manually. The router pattern is formulaic (map HTTP method to controller method with `Depends` wiring). Generate router stubs alongside controller stubs to reduce boilerplate and prevent spec drift.

### Auto-update `__init__.py` re-exports after generation

**Status**: OPEN
**Priority**: LOW
**Источник**: E2E codegen_orchestrator todo_api Level C (2026-03-04)

**Description**: After adding new models, `schemas/__init__.py`, `models/__init__.py`, `repositories/__init__.py` must be manually updated to re-export new classes. The generate command doesn't update these files. Fix: auto-generate these `__init__.py` files or remove the re-export pattern in favor of direct imports.

### `make setup` not idempotent — fails if `.venv` exists

**Status**: DONE
**Priority**: LOW
**Источник**: E2E codegen_orchestrator weather_bot worker audit (2026-03-04)

**Description**: `make setup` fails with "A virtual environment already exists at /workspace/.venv. Use --clear to replace it".

**Fix applied**: `uv venv --quiet 2>/dev/null || uv venv --clear --quiet` в `Makefile.jinja` (коммит `b605d3c`).

### Xenon excludes don't cover service test directories

**Status**: DONE
**Priority**: LOW
**Источник**: E2E codegen_orchestrator weather_bot worker audit (2026-03-04)

**Description**: Makefile xenon uses `--exclude '.framework/*,tests/*'` which only matches root `tests/`, not `services/*/tests/`.

**Fix applied**: Обе xenon-команды обновлены: `--exclude '.framework/*,tests/*,services/*/tests/*'` (коммит `b605d3c`).

---

## Закрытые пункты (архив)

<details>
<summary>Развернуть</summary>

### Remove poetry lock from Backend Dockerfile — DONE
Migrated to uv. Poetry полностью удалён.

### Add `make init` Command — DONE (покрыто `make setup`)
`make setup` — единая точка входа: создаёт venvs, устанавливает зависимости, генерирует код, настраивает git hooks.

### Add `ruff check --fix` to Copier Post-Generation Tasks — DONE (покрыто `make setup`)
`make format` запускается пользователем вручную после `make setup`. Copier `_tasks` больше не запускают генерацию/lint — всё делает `make setup`.

### Makefile.jinja: `ruff format --extend-exclude` — DONE
Excludes перенесены в `ruff.toml`, CLI-флаги убраны.

### Copier _tasks: генерация schemas — DONE (покрыто `make setup`)
Генерация перенесена из copier `_tasks` в `make setup`. Пользователь обязан запустить `make setup` после `copier copy`.

### FutureWarning от datamodel-code-generator — DONE
Добавлен `formatters=[Formatter.RUFF_FORMAT, Formatter.RUFF_CHECK]`.

### E2E Issues iterations 4-5 — DONE
Все 15 issues из iteration 5 закрыты в коммите `5c9128f`.

### `.dockerignore` — DONE
Exists in both root (52 lines) and `template/` (14 lines). Excludes `.venv/`, `__pycache__/`, `.git/`, `node_modules/`, `.env`, `docs/`.

### Frontend Dockerfile: `npm ci` — DONE
All Dockerfiles already use `npm ci` (template frontend + node scaffold).

### Tooling Removal: Migrate to uv — DONE
Tooling container removed. All tools run natively via per-service `.venv/` and root `.venv/`. See `docs/plan-tooling-removal.md`.

### Event Channel Naming Convention — DONE (де-факто)
Конвенция реализована в `EventsGenerator`: snake_case → dot-notation (`user_registered` → `user.registered`).

</details>
