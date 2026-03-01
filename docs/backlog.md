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

### Add E2E CI Job for Unified Handlers

**Status**: TODO
**Priority**: MEDIUM

**Description**: Add a CI job that:
1. Generates a project via copier with dual-transport operations
2. Runs `make setup && make generate-from-spec`
3. Runs `make lint`
4. Runs `make tests`

This would catch integration issues between generated code and user templates.

---

### compose.dev.yml: PATH не включает per-service .venv

**Status**: DONE

**Description**: В `infra/compose.dev.yml.jinja` добавлен `PATH` с per-service `.venv/bin` + стандартный системный PATH из `python:X-slim` для всех трёх сервисов (backend, tg_bot, notifications_worker). Hardcoded PATH вместо `${PATH}` (утечка хостовых путей) или `$$PATH` (не раскрывается).

---

## Jinja Whitespace в шаблонах документации

**Status**: TODO
**Priority**: LOW

**Description**: Шаблоны `TASK.md.jinja`, `CONTRIBUTING.md.jinja`, `ARCHITECTURE.md.jinja` генерируют лишние пустые строки и некорректные отступы из-за whitespace от Jinja conditional blocks. Подробности — в `docs/e2e-issues-iteration6.md` (issues #1-#4, #9). Все функциональные — никакого влияния на работу проекта, только косметика markdown.

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
