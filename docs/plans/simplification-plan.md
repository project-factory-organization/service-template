# Service Template Simplification

> **Задача**: Backlog #1 в codegen_orchestrator — Service Template Simplification & Refactoring
> **Брейншторм**: `codegen_orchestrator/docs/brainstorms/service-template-and-dev-environment.md`
> **Cross-project**: основная работа здесь (service-template), интеграция — в оркестраторе (scaffolder)
> **Status**: ВСЕ 4 ПУНКТА DONE. Остались только косметические доработки Jinja whitespace.

---

## Проблема

Фреймворк был перегружен: 9 кодогенераторов, обязательный PostgreSQL,
тесная связка tg_bot → backend. Простой Telegram-бот был невозможен без полного бэкенда,
а разработка затягивалась на десятки минут из-за лишней инфраструктуры.

---

## ~~Текущее состояние связки backend ↔ tg_bot~~ DONE ✅

**Сделано.** Backend теперь опциональный модуль. Убрали хардкод `backend module is required` из `copier.yml`, заменили на `at least one module must be selected`.

Все три зависимости tg_bot → backend стали условными через Jinja-шаблоны:
- Compose `depends_on: backend` — только при `'backend' in modules`
- `manifest.yaml` → `.jinja` — `consumes: []` без backend (ClientsGenerator не генерирует BackendClient)
- `main.py` → `.jinja` — без backend нет импортов httpx/BackendClient/UserCreate, нет `_sync_user_with_backend()`, `/start` отвечает простым приветствием
- Тесты, документация (AGENTS.md, README.md) — аналогично обёрнуты

Теперь работают три режима: `modules="tg_bot"` (standalone бот), `modules="backend,tg_bot"` (полный стек), `modules="backend"` (только API).

---

## Генераторы — анализ и решения (из 9 → 5) — DONE ✅

### Убрали

| Генератор | LOC | Статус | Заметки |
|-----------|-----|--------|---------|
| **RegistryGenerator** | 102+79 | ✅ Удалён | — |
| **RoutersGenerator** | 117+97 | ✅ Удалён | — |
| **ClientsGenerator** | 203+232 | ✅ Удалён | Вместо него — `ServiceClient` в `shared/shared/http_client.py` (~125 строк). Базовый HTTP-клиент с retry, exponential backoff, context manager. Конкретные клиенты (например, `BackendClient` в tg_bot) наследуются и добавляют 15-20 строк бизнес-методов. |
| **sync_services** | 262 | ✅ Удалён | Compose-файлы теперь Jinja-шаблоны, генерируются copier'ом при создании проекта. |

> **Заметка для оркестратора:** `sync_services` больше нет. Compose-файлы не перегенерируются. Если оркестратор добавляет новый сервис, compose-файлы нужно править вручную или через отдельный механизм. См. backlog "Add Predefined Module to Existing Project".

### Оставили

| Генератор | LOC | Статус | Что делает |
|-----------|-----|--------|------------|
| **SchemasGenerator** | 51 | ✅ Работает | `models.yaml` → Pydantic-модели через `datamodel-code-generator` |
| **EventsGenerator** | 59+24 | ✅ Работает | `events.yaml` → pub/sub functions с lazy broker |
| **EventAdapterGenerator** | 114+83 | ✅ Работает | Session lifecycle (get_session → controller → commit/rollback) |
| **ControllersGenerator** | 85+34 | ✅ Работает | Стартовые стабы с `NotImplementedError` |
| **ProtocolsGenerator** | 91+43 | ✅ Работает | `typing.Protocol` для контроллеров (DI interface) |

### Ключевые выводы из обсуждения

**Архитектура коммуникаций:**
- REST = внешний API (фронтенд, мобилка, бот как клиент)
- Events = внутренняя коммуникация между сервисами (pub/sub через Redis Streams)
- Межсервисный REST — антипаттерн; единственный случай (tg_bot → backend) опционален

**Принцип отбора генераторов:**
- Генерировать код через агентов дорого (токены). Генераторы, которые делают это быстро и бесплатно — оставляем.
- Оставляем то, что обеспечивает **контракты** (schemas, events, protocols) и **сложные паттерны** (session lifecycle в event adapters).
- Убираем то, что производит **механический бойлерплейт** (routers, registry) или **дублирует инфраструктуру** (clients).

**ServiceClient в shared:**
- Retry с exponential backoff, разделение 4xx/5xx, context manager для httpx — полезная утилита.
- Не генератор, а обычный базовый класс в `shared/shared/http_client.py`.
- Наследуется для конкретных клиентов (`BackendClient` и т.д.).

> **Заметка для оркестратора:** `ServiceClient.__aenter__` возвращает `Self` (не базовый `ServiceClient`), что обеспечивает корректную типизацию для mypy при `async with BackendClient() as client:`.

**Итого по LOC:**
- Удалили: 684 LOC генераторов + 408 LOC шаблонов = **1092 строки**
- Добавили: ~125 LOC `ServiceClient` в shared
- Оставили: 400 LOC генераторов + 184 LOC шаблонов (контракты и паттерны)

---

## ~~Пункт 3: Specs опциональны~~ DONE ✅

### Проблема

Specs (models.yaml, events.yaml, domain YAML) — это контракты между сервисами. Для standalone tg_bot без backend контрактов нет, но фреймворк требовал их наличия.

### Принцип

- **Specs = контракты между сервисами.** Один сервис → нет контрактов → specs не нужны.
- **Инфраструктура генерации (`.framework/`) — всегда присутствует.** Хочешь добавить backend → `copier update`, specs появляются, генерация включается.
- **Качество кода enforce'ится всегда**, но scope проверок адаптируется к наличию specs.

### Что сделано

**3.1. Copier: cleanup для standalone** ✅

Вместо Jinja-условий в самих файлах specs — добавлены `_tasks` в `copier.yml` для post-copy удаления:
```yaml
- "{% if 'backend' not in modules %}rm -rf shared/spec shared/shared/generated shared/shared/http_client.py{% endif %}"
- "{% if 'backend' not in modules %}rm -rf services/*/spec{% endif %}"
```

> **Отклонение от плана**: план предлагал обернуть spec-файлы в `{% if %}`, но post-copy cleanup через `_tasks` проще и надёжнее — не нужно трогать каждый YAML/Python файл в `shared/spec/`. Также удаляется `http_client.py` (не было в плане) и `services/*/spec/manifest.yaml` (не было в плане, но нужно для чистого standalone).

> **Заметка для оркестратора:** В standalone (`modules=tg_bot`) после copier copy нет: `shared/spec/`, `shared/shared/generated/`, `shared/shared/http_client.py`, `services/*/spec/`. Пакет `shared` остаётся как пустой editable dependency (только `__init__.py` и `py.typed`). Это не баг — shared нужен для будущего расширения через `copier update`.

**3.2. tg_bot main.py.jinja: standalone = plain PTB бот** ✅

> **Отклонение от плана**: план упоминал aiogram, но шаблон использует python-telegram-bot (PTB). Реализация корректна.

В standalone режиме (`'backend' not in modules`):
- Нет импортов `shared.generated.events`, `shared.generated.schemas`, `httpx`, `ServiceClient`
- Нет event bus, broker lifecycle (post_init/post_shutdown)
- Нет `BackendClient`, `_sync_user_with_backend()`
- `/start` отвечает простым приветствием, без синхронизации с backend
- Тесты аналогично — standalone вариант без mock broker

**3.3. framework/spec/loader.py: graceful при отсутствии specs** ✅

Реализовано по плану. `load_specs()` возвращает пустой `AllSpecs` если `models.yaml` не существует.

**3.4. framework/generate.py: no-op при пустых specs** ✅

Реализовано по плану.

**3.5. enforce_spec_compliance: conditional + scope** ✅

- Skip если нет `shared/spec/models.yaml`
- BaseModel check только в `controllers/`

**3.6. Makefile.jinja и CI: conditional spec targets** ✅

Spec-only targets обёрнуты в `{% if 'backend' in modules %}`: `validate-specs`, `lint-specs`, `generate-from-spec`, `lint-controllers`, `openapi`, `typescript`, `makemigrations`.

> **Отклонение от плана**: план предлагал `{% if %}...{% else %}...{% endif %}` для `lint:` target. В реализации `lint:` использует одну универсальную команду — spec validation tools graceful (печатают "No specs found" и выходят с 0).

**3.7. Документация** ✅

ARCHITECTURE.md, CONTRIBUTING.md, TASK.md, README.md — backend-specific секции обёрнуты в conditionals.

**3.8. Косметика: Jinja whitespace** ✅ (частично)

> **Не было в плане** — обнаружено при тестировании. `{% endif -%}` стирает ВСЕ whitespace (включая пробелы и табы), что ломает Python-отступы, YAML-отступы, Makefile recipe tabs.
>
> Решение: `{% endif -%}` безопасен только на column 0. Для остального — `{% endif %}` + управление blank lines.
>
> **Оставшиеся проблемы:** Лишние пустые строки в TASK.md, CONTRIBUTING.md, ARCHITECTURE.md — косметика, не влияет на функционал. Подробности в `docs/e2e-issues-iteration6.md`.

### Результат

**`modules=tg_bot`:**
```
project/
├── .framework/              ← генераторы готовы к работе
├── shared/shared/           ← без http_client.py, без generated/
├── services/tg_bot/         ← plain PTB бот, свободен в BaseModel
│   └── (без spec/)
├── Makefile                 ← lint = ruff + xenon + graceful spec checks
└── .github/workflows/ci.yml ← без spec generation
```

**`modules=backend,tg_bot`:**
```
project/
├── .framework/
├── shared/
│   ├── spec/models.yaml, events.yaml
│   └── shared/generated/schemas.py, events.py
│   └── shared/http_client.py
├── services/backend/        ← spec-driven, BaseModel enforce в controllers/
├── services/tg_bot/         ← event-driven, uses shared schemas
├── Makefile                 ← lint = ruff + xenon + spec checks
└── .github/workflows/ci.yml ← с spec generation + drift check
```

---

## ~~Пункт 4: Убрать tooling-контейнер~~ DONE ✅

Полностью реализовано. См. [plan-tooling-removal.md](plan-tooling-removal.md).

**Краткий итог:**
- Tooling-контейнер удалён
- Poetry → uv во всех сервисах
- Per-service venvs через `uv sync --frozen`
- Root `.venv/` для framework dev tools (ruff, xenon, framework package)
- `make setup` — единая точка входа (venvs + codegen + git hooks)
- CI использует `astral-sh/setup-uv@v4` + `make setup`

> **Заметка для оркестратора (итерация 4 tooling-removal):** Осталась интеграция на стороне оркестратора: облегчить worker-base образ (убрать предустановленные python-пакеты), добавить uv + uv-cache volume. Подробности и тестирование в [plan-tooling-removal.md](plan-tooling-removal.md) → Итерация 4.

---

## Связь с другими задачами

- **Backlog #2 (Agent Hierarchy)** в оркестраторе — пересечение по pipeline (Architect node, Scaffolder-как-нода). Упрощение шаблона сделано независимо; интеграция с новым pipeline — второй этап.
- **Backlog #4 (CI Pipeline Redesign)** — шаблон генерирует ci.yml для проектов. Слабое пересечение, не блокирует.
- **Блокеров нет.**

---

## Приоритеты реализации — итоговый статус

| # | Что делали | Статус |
|---|------------|--------|
| 1 | Сделать backend опциональным в copier.yml (standalone tg_bot) | ✅ DONE |
| 2 | Убрать RoutersGenerator, ClientsGenerator, RegistryGenerator, sync_services; добавить ServiceClient в shared | ✅ DONE |
| 3 | Сделать specs опциональными | ✅ DONE |
| 4 | Убрать tooling-контейнер, перейти на `uv` + нативные venvs | ✅ DONE (service-template). TODO: интеграция в оркестратор |

---

## Сводка для оркестратора

Ключевые изменения, которые затрагивают интеграцию:

1. **Pipeline после copier copy:** `copier copy --trust` → `make setup` (обязательно!) → проект готов к `make lint/test/etc`
2. **Нет sync_services:** compose-файлы не перегенерируются. Добавление сервисов требует ручной правки compose или отдельного механизма.
3. **Нет RoutersGenerator:** агент пишет routers вручную. Protocols и controllers генерируются как стабы.
4. **Нет ClientsGenerator:** `ServiceClient` в shared — базовый класс. Конкретные клиенты наследуются и пишутся вручную.
5. **Lazy broker:** `from shared.generated.events import get_broker` — broker создаётся при первом вызове, не при import. Безопасно для тестов.
6. **Per-service venvs:** Каждый сервис имеет свой `.venv/`. Root `.venv/` — для framework tools. Тесты запускаются через `services/*/.venv/bin/pytest`.
7. **Python version:** Управляется через copier variable `python_version` (default: 3.12). Подставляется в Dockerfiles, mypy.ini, pyproject.toml.
8. **Worker-base образ:** Нужен только uv + Python. Все инструменты устанавливаются `make setup` в per-project venvs. Рекомендуется shared uv-cache volume.
