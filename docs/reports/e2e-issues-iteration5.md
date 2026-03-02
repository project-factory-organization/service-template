# E2E Test Report — Iteration 5

**Date:** 2026-02-28
**Commit:** `a05cc98` (chore: disable copier tests in pre-push hook)
**Copier:** 9.12.0
**Template version:** 0.1.0.post120.dev0+a05cc98
**uv:** 0.10.4
**Python:** 3.12.8
**Ruff:** 0.11.4 (installed by uv)

## Test Matrix

| Config | Modules | copier | setup | generate | lint | format | typecheck | tests | xenon |
|--------|---------|--------|-------|----------|------|--------|-----------|-------|-------|
| backend | `backend` | OK | OK | OK | **FAIL** | **CHANGES** | OK | OK (9) | OK |
| standalone | `tg_bot` | OK | OK | — | **FAIL** | **CHANGES** | OK | OK (2) | OK |
| fullstack | `backend,tg_bot` | OK | OK | OK | OK | OK | OK | OK (24) | OK |
| full | `backend,tg_bot,notifications` | OK | OK | OK | OK | OK | OK | OK (28) | OK |

**Прогресс vs предыдущий отчёт (iteration 4):** mypy typecheck теперь зелёный во всех конфигурациях (был FAIL в 3/4). Появились регрессии в lint и format для backend и standalone.

---

## Проблемы

### #1 — lint: unused imports в `tests/conftest.py` (backend)

**Severity:** MEDIUM (блокирует `make lint`)
**Configs:** backend

**File:** `tests/conftest.py`

```
F401 `collections.abc.Generator` imported but unused
F401 `os` imported but unused
F401 `pytest` imported but unused
```

**Причина:** В итерации 4 (#10) удалили SQLAlchemy block из `conftest.py.jinja`, но импорты `Generator`, `os`, `pytest` остаются безусловно в шаблоне. Redis fixtures (которые используют эти импорты) рендерятся только при `tg_bot or notifications in modules`. В backend-only конфигурации conftest.py содержит 3 неиспользуемых импорта и пустое тело.

**Фикс:** Обернуть импорты `os` и `Generator` в тот же `{% if %}` что и redis fixtures. Минимально — сделать все импорты условными по `tg_bot or notifications`.

---

### #2 — lint: unused `Generator` import в `test_command_handler.py` (standalone)

**Severity:** MEDIUM (блокирует `make lint`)
**Configs:** standalone

**File:** `services/tg_bot/tests/unit/test_command_handler.py:5`

```
F401 `collections.abc.Generator` imported but unused
```

**Причина:** В итерации 4 (#5) добавили `from collections.abc import Generator` для аннотации yield-fixtures (`mock_broker`, `mock_publish`, `mock_sync_user`). Но эти fixtures рендерятся только при `backend in modules` — в standalone конфигурации (`tg_bot` only) нет yield-fixtures, и `Generator` остаётся неиспользуемым.

**Фикс:** Обернуть `from collections.abc import Generator` в `{% if 'backend' in modules %}` в шаблоне `test_command_handler.py.jinja`.

---

### #3 — `notifications_worker` отсутствует в `compose.base.yml`

**Severity:** HIGH (блокирует `make prod-start`)
**Configs:** full

`compose.prod.yml` ссылается на `notifications_worker` через `extends: compose.base.yml / service: notifications_worker`, но в `compose.base.yml.jinja` нет определения сервиса `notifications_worker`.

```
cannot extend service "notifications_worker": service "notifications_worker" not found in compose.base.yml
```

Также `compose.dev.yml.jinja` не содержит `notifications_worker` — в dev-режиме сервис вообще не запустится.

**Причина:** При создании шаблонов для compose файлов `notifications_worker` забыли добавить в `compose.base.yml.jinja` и `compose.dev.yml.jinja`.

**Фикс:** Добавить блок `{% if 'notifications' in modules %}` с определением `notifications_worker` в `compose.base.yml.jinja` и `compose.dev.yml.jinja`.

---

### #4 — Dockerfile: hardcoded `python:3.11-slim` при `python_version=3.12`

**Severity:** MEDIUM
**Configs:** все

Все Dockerfiles (`services/backend/Dockerfile`, `services/tg_bot/Dockerfile`, `services/notifications_worker/Dockerfile`) содержат:

```dockerfile
FROM python:3.11-slim AS base
```

При этом copier настроен с `python_version: "3.12"` (default), CI использует `python-version: "3.12"`, root `pyproject.toml` — `requires-python = ">=3.12"`.

Docker образ собирается с Python 3.11, а CI и local dev используют 3.12.

**Причина:** Dockerfiles — статические файлы (не `.jinja`), переменная `python_version` из copier не подставляется.

**Варианты:**
- Переименовать в `Dockerfile.jinja` и использовать `{{ python_version }}`
- Или обновить hardcode до `python:3.12-slim`
- Или использовать build arg: `ARG PYTHON_VERSION=3.12` → `FROM python:${PYTHON_VERSION}-slim`

---

### #5 — `mypy.ini`: hardcoded `python_version = 3.11`

**Severity:** LOW
**Configs:** все

`mypy.ini` (не `.jinja`) содержит `python_version = 3.11`, но проект генерируется с `python_version = 3.12`.

**Причина:** Тот же паттерн что #4 — статический файл, `python_version` из copier не подставляется.

**Фикс:** Переименовать в `mypy.ini.jinja` и использовать `{{ python_version }}`, или обновить hardcode.

---

### #6 — `requires-python` mismatch: root `>=3.12` vs services `>=3.11`

**Severity:** LOW (не блокирует)
**Configs:** все

- Root `pyproject.toml`: `requires-python = ">=3.12"`
- `services/backend/pyproject.toml`: `requires-python = ">=3.11"`
- `services/tg_bot/pyproject.toml`: `requires-python = ">=3.11"`
- `services/notifications_worker/pyproject.toml`: `requires-python = ">=3.11"`

**Причина:** Root pyproject.toml — `.jinja`-менее файл (не шаблон), но hardcoded `>=3.12`. Сервисные pyproject.toml — тоже статические, hardcoded `>=3.11`. Версия Python из copier не передаётся ни туда, ни туда.

---

### #7 — `infra/.env.test` содержит Postgres-переменные в standalone

**Severity:** LOW (не блокирует)
**Configs:** standalone

`infra/.env.test` содержит:
```
POSTGRES_DB=service_template_test
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/service_template_test
```

В standalone нет ни PostgreSQL, ни backend. Файл — лишний артефакт.

**Причина:** `infra/.env.test` — статический файл (не `.jinja`), генерируется одинаково для всех конфигураций.

**Фикс:** Либо сделать `.env.test.jinja` с условным блоком для postgres, либо оставить (не блокирует).

---

### #8 — `pre-push` hook: `make generate-from-spec` в standalone

**Severity:** LOW (не блокирует в обычном случае)
**Configs:** standalone

`.githooks/pre-push` содержит unconditional `make generate-from-spec` при изменении `shared/` или `.framework/`. В standalone этот make-target не существует:
```
make: *** No rule to make target 'generate-from-spec'.  Stop.
```

На практике в standalone пользователь вряд ли изменит `shared/` (файлов мало), но потенциально может сломать push.

**Причина:** `pre-push` — статический файл (не `.jinja`), не адаптируется к конфигурации.

**Фикс:** Добавить `if make -n generate-from-spec >/dev/null 2>&1; then` guard перед вызовом, или сделать `.jinja`.

---

### #9 — `TASK.md`: `make generate` вместо `make generate-from-spec`

**Severity:** LOW (косметика / misleading docs)
**Configs:** все

`TASK.md.jinja` содержит:
```
# Generate code from specs
make generate
```

Но реальный target — `make generate-from-spec`. `make generate` вернёт ошибку.

**Фикс:** Заменить `make generate` на `make generate-from-spec` в шаблоне.

---

### #10 — `.env.example`: лишние пустые строки от Jinja-рендеринга

**Severity:** LOW (косметика)
**Configs:** все

`.env.example` содержит 3-5 последовательных пустых строк в местах, где Jinja conditional blocks не рендерятся. Пример для backend:
```
POSTGRES_REQUIRE_SSL=false



                          <-- 3+ пустые строки от нерендеренных tg_bot/notifications блоков

# Backend API URL...
```

**Причина:** `{% if %}` blocks в `.env.example.jinja` оставляют пустые строки. Нужны `{%- if -%}` для trim whitespace.

**Варианты:**
- Использовать `-%}` / `{%-` для trim
- Или оставить (косметика, не влияет на функционал)

---

### #11 — Избыточные пустые строки в compose YAML и `services.yml`

**Severity:** LOW (косметика)
**Configs:** все

Файлы `compose.base.yml`, `compose.dev.yml`, `compose.prod.yml`, `services.yml`, `.github/workflows/ci.yml` содержат 3+ последовательных пустых строк от Jinja conditional blocks.

**Причина:** Та же что #10 — Jinja whitespace control.

---

### #12 — `ARCHITECTURE.md`: "DB" в standalone

**Severity:** LOW (косметика)
**Configs:** standalone

```
They communicate only via defined APIs or shared infrastructure (DB, Queue).
```

Standalone не использует DB (PostgreSQL). Строка с "(DB, Queue)" рендерится безусловно.

**Причина:** В `ARCHITECTURE.md.jinja` строка с `(DB, Queue)` не обёрнута в conditional. Было исправлено для `Queue` (условие на tg_bot/notifications), но `DB` осталось.

**Фикс:** Сделать conditional: `({% if 'backend' in modules %}DB{% if 'tg_bot' in modules or 'notifications' in modules %}, {% endif %}{% endif %}{% if 'tg_bot' in modules or 'notifications' in modules %}Queue{% endif %})` или перефразировать.

---

### #13 — `CONTRIBUTING.md`: упоминания shared code и code generator в standalone

**Severity:** LOW (косметика)
**Configs:** standalone

`CONTRIBUTING.md` содержит секции, нерелевантные для standalone:
- "Stale Shared Code" — `shared/` mount в compose
- "Type Mismatches: The code generator supports `list[type]`..."
- "Dockerfile Copies: COPY sources... use `shared/`"

**Причина:** `CONTRIBUTING.md.jinja` не имеет достаточных conditional blocks для backend-specific советов.

---

### #14 — `BACKEND_API_URL` в backend-only `.env.example`

**Severity:** LOW (косметика)
**Configs:** backend

`.env.example` содержит `BACKEND_API_URL=http://backend:8000`. Эта переменная используется для service-to-service вызовов (tg_bot → backend), но в backend-only конфигурации некому вызывать backend по этому URL.

**Причина:** Условие в `.env.example.jinja` — `{% if 'backend' in modules %}`, но логически `BACKEND_API_URL` нужен только при наличии клиентских сервисов (tg_bot, notifications).

**Фикс:** Изменить условие на `{% if 'backend' in modules and ('tg_bot' in modules or 'notifications' in modules) %}` или оставить (не мешает).

---

### #15 — `shared/` пакет без содержимого в standalone

**Severity:** LOW (не блокирует)
**Configs:** standalone

Уже описано в iteration 4 (#13). Copier `_tasks` удаляет `shared/spec/`, `shared/shared/generated/`, `shared/shared/http_client.py`, но остаётся:
```
shared/
  pyproject.toml
  shared/
    __init__.py
    py.typed
```

Пустой пакет `shared` устанавливается как editable dependency и не несёт функционала.

---

## Что работает хорошо

1. **copier copy** — все 4 конфигурации генерируются чисто, `_tasks` корректно удаляют ненужные модули
2. **make setup** — venvs создаются без ошибок и warnings во всех конфигурациях
3. **make generate-from-spec** — генерация schemas, protocols, events чистая, без FutureWarning, без spurious `Model(RootModel[Any])`
4. **mypy typecheck** — **полностью зелёный** во всех конфигурациях (vs 3 FAIL в iteration 4)
5. **make tests** — все тесты проходят: 9 backend, 2 standalone, 15 fullstack tg_bot, 4 notifications, total 28 в full
6. **xenon** — complexity check проходит во всех конфигурациях
7. **Python syntax** — все `.py` файлы синтаксически корректны
8. **Lazy broker** — `get_broker()` работает, тесты с mock проходят
9. **Framework lint tools** — gracefully skip в standalone (нет specs)
10. **Docker Compose standalone** — `compose.dev.yml` валиден, `tg_bot` запускается без profiles

## Резюме

| Severity | Count | Суть |
|----------|-------|------|
| HIGH | 1 | notifications_worker отсутствует в compose (#3) |
| MEDIUM | 3 | lint failures от unused imports (#1, #2), Dockerfile Python version (#4) |
| LOW | 11 | mypy.ini version, requires-python mismatch, .env.test, pre-push hook, TASK.md, blank lines, docs косметика, shared/ package |

**Основной вывод:** mypy полностью зелёный — прогресс vs iteration 4. Главные проблемы: (1) `notifications_worker` отсутствует в compose — **блокер для full config production**, (2) lint регрессии в backend и standalone из-за неаккуратных условных импортов в шаблонах, (3) несоответствие Python version между Dockerfile (3.11) и остальным проектом (3.12).
