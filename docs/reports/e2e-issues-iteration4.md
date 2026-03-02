# E2E Test Report — Iteration 4 (Post Lazy-Broker Fixes)

**Date:** 2026-02-28
**Commit:** `34f425e` (fix: resolve remaining E2E issues from lazy broker migration)
**Copier:** 9.12.0
**Template version:** 0.1.0.post115.dev0+34f425e

## Test Matrix

| Config | Modules | copier | setup | generate | lint | format | typecheck | tests | xenon |
|--------|---------|--------|-------|----------|------|--------|-----------|-------|-------|
| backend | `backend` | OK | OK | OK | OK | OK | **FAIL** | OK (9) | OK |
| standalone | `tg_bot` | OK | OK | — | OK | OK | OK | OK (2) | OK |
| fullstack | `backend,tg_bot` | OK | OK | OK | OK | OK | **FAIL** | OK (24) | OK |
| full | `backend,tg_bot,notifications` | OK | OK | OK | OK | OK | **FAIL** | OK (28) | OK |

**Прогресс vs предыдущий отчёт (iteration 3):** copier copy, make setup, generate-from-spec, lint, format, tests — всё зелёное во всех конфигурациях. Единственный красный столбец — typecheck (mypy).

---

## Проблемы

### #1 — mypy: `Settings()` без обязательных аргументов (backend)

**Severity:** MEDIUM
**Configs:** backend, fullstack, full
**File:** `services/backend/src/core/settings.py:116`

```
error: Missing named argument "app_name" for "Settings"  [call-arg]
error: Missing named argument "environment" for "Settings"  [call-arg]
error: Missing named argument "app_secret_key" for "Settings"  [call-arg]
error: Missing named argument "postgres_host" for "Settings"  [call-arg]
... (8 errors total)
```

**Причина:** `get_settings()` вызывает `Settings()` без аргументов. `Settings` наследует `pydantic_settings.BaseSettings` — значения приходят из `.env` / env vars, но mypy не знает про `model_config = SettingsConfigDict(env_prefix=...)` и считает поля обязательными параметрами конструктора.

**Варианты фикса:**
- Добавить `# type: ignore[call-arg]` на строку `Settings()`
- Или сделать поля `Optional` с `None` default + валидацию в `model_validator`
- Или добавить mypy plugin для pydantic-settings

---

### #2 — mypy: `_Call | None` has no attribute `args` (backend tests)

**Severity:** LOW
**Configs:** backend, fullstack, full
**File:** `services/backend/tests/unit/test_debug.py:50`

```
error: Item "None" of "_Call | None" has no attribute "args"  [union-attr]
```

**Причина:** `publish_mock.await_args` может быть `None` (mypy учитывает этот тип), а код обращается к `.args` без проверки. В тестах `assert_awaited_once()` гарантирует что `await_args` не `None`, но mypy этого не знает.

**Фикс:** `assert publish_mock.await_args is not None` перед обращением к `.args`.

---

### #3 — mypy: `Function is missing a return type annotation` (backend tests)

**Severity:** LOW
**Configs:** backend, fullstack, full
**File:** `services/backend/tests/unit/test_events.py:15`

```
error: Function is missing a return type annotation  [no-untyped-def]
```

**Причина:** `async def test_publish_user_registered():` без `-> None`.

**Фикс:** Добавить `-> None`.

---

### #4 — mypy: `ServiceClient` has no attribute `create_user` (tg_bot)

**Severity:** MEDIUM
**Configs:** fullstack, full
**File:** `services/tg_bot/src/main.py:82`

```
error: "ServiceClient" has no attribute "create_user"  [attr-defined]
```

**Причина:** `ServiceClient.__aenter__` возвращает `-> ServiceClient` вместо `-> Self`. При `async with BackendClient() as client:` mypy видит тип `client` как `ServiceClient` (базовый класс), а не `BackendClient`. Метод `create_user` определён только на `BackendClient`.

**Фикс:** В `shared/shared/http_client.py` изменить:
```python
async def __aenter__(self) -> ServiceClient:  # было
async def __aenter__(self) -> Self:           # нужно (from typing import Self)
```

---

### #5 — mypy: Generator return type для pytest fixtures (tg_bot tests)

**Severity:** LOW
**Configs:** fullstack, full
**File:** `services/tg_bot/tests/unit/test_command_handler.py:14,24,295`

```
error: The return type of a generator function should be "Generator" or one of its supertypes  [misc]
```

**Причина:** Fixtures с `yield` аннотированы как `-> MagicMock` / `-> AsyncMock`, а mypy требует `Generator[MagicMock, None, None]`.

**Фикс:** Изменить return type на `Generator[MagicMock, None, None]` (или убрать аннотацию, pytest fixtures не требуют).

---

### #6 — mypy: `_Call | None` not indexable (tg_bot tests)

**Severity:** LOW
**Configs:** fullstack, full
**File:** `services/tg_bot/tests/unit/test_command_handler.py:64`

```
error: Value of type "_Call | None" is not indexable  [index]
```

**Причина:** `mock_publish.await_args[0][0]` — `await_args` может быть `None`. Та же проблема что #2, но через `[]` вместо `.args`.

**Фикс:** `assert mock_publish.await_args is not None` перед индексацией.

---

### #7 — README.md: некорректный Tech Stack для standalone

**Severity:** LOW (косметика)
**Configs:** standalone

README standalone-конфигурации (`modules=tg_bot`) содержит:
```
- **FastAPI** + **Pydantic** (spec-first)
- **PostgreSQL** + **SQLAlchemy** + **Alembic**
```

Эти технологии не используются в standalone (нет backend). Также:
- "Development Workflow" показывает `Add/modify models` и `Add endpoints` которые не применимы без backend
- `generate-from-spec` упоминается в workflow но отсутствует в Makefile

**Причина:** `README.md.jinja` не обёрнут в `{% if 'backend' in modules %}` для строк с FastAPI/PostgreSQL/spec workflow.

---

### #8 — ARCHITECTURE.md: упоминание удалённого Tooling Container

**Severity:** LOW (косметика)
**Configs:** все

```
Rule: Nothing runs on the host machine except docker, make, and git.
Tooling Container: We use a dedicated tooling service in docker-compose...
```

**Причина:** После итерации 2 (tooling removal) tooling контейнер был удалён, инструменты запускаются нативно через `uv`/`.venv`. Шаблон `ARCHITECTURE.md.jinja` не обновлён.

---

### #9 — Docker Compose: `make dev-start` не запускает tg_bot

**Severity:** MEDIUM
**Configs:** standalone, fullstack, full

`tg_bot` в `services.yml` имеет `profiles: ["tg"]`. Docker Compose с профилями не включает сервис в `docker compose up` без `--profile tg` или `COMPOSE_PROFILES=tg`.

В standalone это особенно критично: `make dev-start` поднимает только redis, но не tg_bot — единственный сервис проекта.

**Причина:** `profiles` — правильный механизм для optional-сервисов в fullstack (бот не обязателен), но в standalone конфигурации tg_bot должен стартовать по умолчанию.

**Варианты:**
- Не использовать profiles для tg_bot в standalone (убрать `profiles:` из services.yml.jinja когда tg_bot — единственный модуль)
- Или добавить `COMPOSE_PROFILES=tg` в Makefile dev-start
- Или задокументировать: `make dev-start` + `--profile tg`

---

### #10 — `shared.generated.database` не существует (conftest.py)

**Severity:** LOW (не блокирует)
**Configs:** backend, fullstack, full

`tests/conftest.py` импортирует `from shared.generated.database import Base`, но `database.py` не генерируется фреймворком. Импорт обёрнут в `try/except ImportError`, так что runtime ошибок нет, но:
- `db_session` fixture никогда не определяется
- Интеграционные тесты, использующие `db_session`, не будут работать

**Причина:** Фреймворк генерирует `schemas.py` и `events.py`, но не `database.py`. SQLAlchemy модели (`services/backend/src/app/models/`) создаются вручную. `conftest.py` ожидает общий `Base`, но его нет в generated коде.

**Варианты:**
- Генерировать `database.py` с `Base = declarative_base()` из models spec
- Или исправить conftest для импорта Base из правильного места (backend app models)
- Или убрать db_session fixture из root conftest (он нужен только в backend/tests/conftest.py)

---

### #11 — Лишний `class Model(RootModel[Any])` в сгенерированных schemas

**Severity:** LOW (косметика)
**Configs:** backend, fullstack, full

```python
class Model(RootModel[Any]):
    root: Any
```

Этот класс — артефакт `datamodel-code-generator`. Он не используется нигде и засоряет namespace.

**Причина:** `datamodel-code-generator` создаёт `Model` для root-level JSON Schema объекта. Требуется post-processing сгенерированного файла или настройка генератора.

---

### #12 — `backend` .env.example содержит `REDIS_URL` без Redis в compose

**Severity:** LOW (косметика)
**Configs:** backend

`.env.example` содержит `REDIS_URL=redis://redis:6379`, но в backend-only конфигурации нет redis service в compose файлах. Redis нужен для `faststream[redis]` (event publishing), но без tg_bot/notifications сервиса, события некому обрабатывать.

**Причина:** `.env.example.jinja` включает `REDIS_URL` когда есть backend (т.к. backend использует faststream), но compose не включает redis service без tg_bot/notifications.

---

### #13 — standalone: `shared/spec/` и `shared/shared/generated/` удалены, но `shared/` пакет остаётся

**Severity:** LOW (не блокирует)
**Configs:** standalone

Copier `_tasks` удаляет `shared/spec`, `shared/shared/generated`, `shared/shared/http_client.py` для конфигураций без backend. Остаётся:
```
shared/
  pyproject.toml
  shared/
    __init__.py
    py.typed
```

Пустой пакет `shared` не несёт функционала, но устанавливается как editable dependency в tg_bot venv. Не блокирует, но лишний мусор.

---

## Что работает хорошо

1. **copier copy** — чисто генерирует все 4 конфигурации, _tasks корректно удаляют ненужные сервисы
2. **make setup** — устанавливает venv, per-service venvs, генерирует код, настраивает git hooks — полный цикл без ошибок
3. **make generate-from-spec** — генерация schemas, protocols, events без FutureWarning (ранее был)
4. **make lint** — проходит чисто (ruff + xenon + spec validation + controller sync)
5. **make format** — не меняет файлы (шаблоны генерируют чистый код)
6. **make tests** — все unit тесты проходят (9 backend, 2 standalone tg_bot, 15 fullstack tg_bot, 4 notifications)
7. **Per-service venvs** — корректно создаются и используются
8. **Lazy broker** — get_broker() работает, тесты с mock_broker проходят

## Резюме

| Severity | Count | Суть |
|----------|-------|------|
| MEDIUM | 3 | mypy Settings, mypy ServiceClient Self, docker profiles |
| LOW | 10 | mypy тесты (4), README/ARCHITECTURE docs (2), database.py, Model artifact, REDIS_URL, empty shared |

**Основной вывод:** Pipeline от copier copy → make setup → lint → tests полностью зелёный. Единственная проблемная область — **mypy typecheck**, в основном из-за pydantic-settings и mock typing. Docker profiles для tg_bot требуют внимания в standalone.
