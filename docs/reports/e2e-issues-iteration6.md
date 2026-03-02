# E2E Issues — Iteration 6

**Date:** 2026-02-28
**Commit:** `5c9128f` (fix: resolve all 15 E2E issues from iteration 5)
**Copier:** 9.12.0 | **Python:** 3.12.3 | **uv:** 0.10.4 | **Ruff:** 0.15.1 | **Docker:** 29.2.1

## Test Matrix

| Stage            | backend | standalone | fullstack | full |
|------------------|---------|------------|-----------|------|
| copier           | OK      | OK         | OK        | OK   |
| setup            | OK      | OK         | OK        | OK   |
| generate         | OK      | N/A        | OK        | OK   |
| lint             | OK      | OK         | OK        | OK   |
| format           | OK      | OK         | OK        | OK   |
| typecheck        | OK      | OK         | OK        | OK   |
| tests            | OK      | OK         | OK        | OK   |
| xenon            | OK      | OK         | OK        | OK   |
| validate-specs   | OK      | N/A        | OK        | OK   |

Все ключевые проверки проходят с exit 0 во всех конфигурациях. Ниже — найденные отклонения от идеала.

---

## #1 — TASK.md: лишние пустые строки из Jinja-блоков

**Severity:** MEDIUM (косметика, но видна пользователю сразу)
**Affected:** все конфигурации
**File:** `template/TASK.md.jinja`

Между секциями "Files to Focus On" и "Commands" рендерятся 3–6 подряд идущих пустых строк. В backend-only наиболее заметно (строки 28–34 — 6 пустых строк подряд).

**Пример (backend):**
```
### Backend
- `services/backend/src/app/` - Business logic
...


          ← 6 пустых строк


## Commands
```

**Root cause:** Условные блоки `{% if 'tg_bot' in modules %}...{% endif %}`, `{% if 'notifications' in modules %}...{% endif %}` и т.д. рендерятся как пустые строки, когда модуль не выбран. Шаблон не использует `{%-` для whitespace control.

**Fix:** Переписать условные блоки в TASK.md.jinja с `{%-` тегами, аналогично тому как это сделано в `.env.example.jinja`.

---

## #2 — CONTRIBUTING.md: пропущены пустые строки перед заголовками

**Severity:** MEDIUM (ломает рендеринг в некоторых Markdown-парсерах)
**Affected:** все конфигурации
**File:** `template/CONTRIBUTING.md.jinja`

Три места, где заголовок следует сразу после контента без разделяющей пустой строки:

**a)** Строка 12 (все конфиги) — `## 2. Code Style & Standards` идёт сразу после буллет-листа:
```
- `make generate-from-spec`: Generates code from YAML specs.
## 2. Code Style & Standards
```

**b)** Строка 38 (fullstack, full) — `### Testing` без пустой строки:
```
4.  Update service code to use the new generated models/routers.
### Testing
```

**c)** Строка 29 (standalone) — `### Testing` без пустой строки:
```
3.  Implement the business logic.
### Testing
```

**Root cause:** В шаблоне строка 10 `{% if 'backend' in modules -%}` и строка 13 `{% endif -%}` — теги `-%}` съедают перенос строки после себя, и пустая строка перед `## 2.` пропадает. Аналогично строка 41 `{% endif -%}` перед `### Testing`.

**Fix:** Заменить `{% endif -%}` на `{%- endif %}` в соответствующих местах, либо добавить пустую строку после закрывающего тега, вне зоны действия `-%}`.

---

## #3 — ARCHITECTURE.md: пропущена пустая строка перед `## Service Modules`

**Severity:** MEDIUM
**Affected:** backend, fullstack, full (где есть Spec-First Flow секция)
**File:** `template/ARCHITECTURE.md.jinja:20`

```
3.  **Implement:** Services import these generated assets...
## Service Modules
```

**Root cause:** Строка 20 шаблона `{% endif -%}` съедает перенос строки, пустая строка между секциями пропадает.

**Fix:** Поменять `{% endif -%}` → `{%- endif %}` либо добавить пустую строку вне зоны действия `-%}`.

---

## #4 — ARCHITECTURE.md: Directory Structure — потеряна вложенность сервисов

**Severity:** MEDIUM (дезориентирует читателя)
**Affected:** все конфигурации кроме standalone (у standalone только один сервис)
**File:** `template/ARCHITECTURE.md.jinja:56-67`

Сервисы должны быть вложенными пунктами под `services/`, но рендерятся на том же уровне:

**Ожидалось:**
```markdown
- `services/`: Source code for individual microservices.
  - `backend/`: FastAPI REST API with PostgreSQL.
  - `tg_bot/`: Telegram bot (FastStream worker).
```

**Фактически:**
```markdown
- `services/`: Source code for individual microservices.
- `backend/`: FastAPI REST API with PostgreSQL.
- `tg_bot/`: Telegram bot (FastStream worker).
```

**Root cause:** Тег `{% if 'backend' in modules -%}` (с `-%}`) съедает ВСЮ whitespace после себя, включая перенос строки и ведущие 2 пробела на следующей строке. `  - \`backend/\`` теряет indentation.

**Fix:** Использовать `-%}` аккуратно — либо не использовать `-%}` и вместо этого сдвинуть контент на ту же строку с тегом, либо переписать блок без `-%}` на тегах (и получить лишнюю пустую строку как меньшее зло), либо вынести сервисы из условных блоков и сделать один inline-conditional для всего блока.

---

## #5 — ARCHITECTURE.md: ссылка на несуществующую директорию `templates/`

**Severity:** LOW
**Affected:** все конфигурации
**File:** `template/ARCHITECTURE.md.jinja:73`

```markdown
- `templates/`: Jinja2 templates for scaffolding new services.
```

Директория `templates/` не существует в сгенерированном проекте. Фактический путь — `.framework/framework/templates/`.

**Root cause:** Строка захардкожена в шаблоне, не обновлялась после реструктуризации.

**Fix:** Заменить на `- \`.framework/\`: Framework internals (templates, codegen, scaffolding).` или убрать строку.

---

## #6 — .env vs .env.example: рассогласование ключей в backend-only

**Severity:** MEDIUM
**Affected:** только backend
**File:** `template/.env.jinja` vs `template/.env.example.jinja`

В backend-only конфигурации `.env` содержит `REDIS_URL` и `BACKEND_API_URL`, а `.env.example` — нет.

| Ключ | `.env` условие | `.env.example` условие |
|------|---------------|----------------------|
| `REDIS_URL` | `backend OR tg_bot OR notifications` | `tg_bot OR notifications` |
| `BACKEND_API_URL` | `backend` | `backend AND (tg_bot OR notifications)` |

**Root cause:** `.env.jinja` строка 18 включает `REDIS_URL` для backend (т.к. `events.py` использует `get_broker()` с `REDIS_URL`), а `.env.example.jinja` строка 22 — только для tg_bot/notifications. Аналогично для `BACKEND_API_URL` — в `.env.jinja` строка 21 достаточно `backend`, а в `.env.example.jinja` строка 27 требуется ещё tg_bot/notifications.

**Fix:** Синхронизировать условия. `REDIS_URL` в `.env.example` нужен, если есть backend (для events) ИЛИ tg_bot/notifications. `BACKEND_API_URL` — только если backend И (tg_bot ИЛИ notifications), как сейчас в .env.example (правильнее). Значит `.env.jinja` нужно ужесточить.

---

## #7 — compose.base.yml: ведущая пустая строка

**Severity:** LOW (косметика)
**Affected:** backend, fullstack, full (все конфиги с backend)
**File:** `template/infra/compose.base.yml.jinja:1`

Файл начинается с пустой строки перед `x-backend-env:`.

**Root cause:** Шаблон строка 1: `{%- if 'backend' in modules %}` — тег `{%-` съедает whitespace ПЕРЕД ним (но перед ним ничего нет), а `%}` без `-` оставляет перенос строки ПОСЛЕ себя. В итоге первая строка файла — пустая.

**Fix:** Заменить на `{%- if 'backend' in modules -%}` (добавить `-%}` для первого тега).

---

## #8 — Pre-push hook: мёртвый путь `^specs/`

**Severity:** LOW
**Affected:** все конфигурации
**File:** `template/.githooks/pre-push:52-55`

```bash
# specs/ requires regeneration
if echo "$changed_files" | grep -qE '^specs/'; then
  run_generate=true
fi
```

Директория `specs/` не существует ни в одной конфигурации. Спеки лежат в `shared/spec/`. Этот код никогда не сработает.

**Root cause:** Путь не обновлён после переименования. Изменения в `shared/spec/` всё же ловятся через `^shared/` на строке 41, так что функционально это не баг, но dead code.

**Fix:** Поменять `'^specs/'` → `'^shared/spec/'`, либо убрать блок целиком (т.к. `^shared/` уже ловит этот случай).

---

## #9 — ARCHITECTURE.md: лишняя пустая строка перед Unified Handlers

**Severity:** LOW (косметика)
**Affected:** fullstack, full
**File:** `template/ARCHITECTURE.md.jinja:83`

```markdown
- **Redis:** Message broker for async event processing.


## Unified Handlers
```

Между "Infrastructure Components" и "Unified Handlers" — 2 пустых строки вместо одной.

**Root cause:** Строка 83 шаблона `{% if 'backend' in modules and ('tg_bot'...) %}` без `{%-` рендерится как пустая строка + естественная пустая строка перед `## Unified Handlers`.

**Fix:** Добавить `{%-` на открывающий тег.

---

## #10 — ARCHITECTURE.md: `default` service type присутствует во всех конфигурациях

**Severity:** INFO
**Affected:** все конфигурации
**File:** `template/ARCHITECTURE.md.jinja:40`

```markdown
- `default`: Generic container placeholder.
```

Тип `default` указан во всех конфигурациях, но ни один сгенерированный сервис его не использует. Потенциально сбивает с толку.

**Root cause:** Строка не обёрнута в условие.

**Fix:** Убрать или обернуть в Jinja-условие, либо оставить как справочную информацию (самый простой вариант).

---

## #11 — conftest.py: os.getenv с дефолтом противоречит CONTRIBUTING.md

**Severity:** INFO
**Affected:** standalone, fullstack, full (конфиги с redis)
**File:** `template/tests/conftest.py.jinja`

```python
return os.getenv("TEST_REDIS_URL", "redis://localhost:6379/15")
```

CONTRIBUTING.md (секция 5) декларирует: «NEVER use default values in `os.getenv("VAR", "default")`». Тестовый conftest нарушает это правило.

**Root cause:** Правило было написано для production-кода. В тестовых фикстурах дефолты допустимы, но формально contradicts собственные guidelines.

**Fix:** Либо добавить исключение в CONTRIBUTING.md (пример: «In test fixtures, defaults are acceptable»), либо убрать дефолт из conftest.

---

## Итого

| Severity | # | Описание |
|----------|---|----------|
| MEDIUM   | 4 | #1 TASK.md blank lines, #2 CONTRIBUTING.md headings, #3 ARCHITECTURE.md heading, #4 Directory Structure indentation |
| MEDIUM   | 1 | #6 .env/.env.example key mismatch |
| LOW      | 4 | #5 templates/ reference, #7 compose leading blank, #8 pre-push dead path, #9 ARCHITECTURE.md blank line |
| INFO     | 2 | #10 default service type, #11 conftest.py vs guidelines |

### Что работает хорошо

- Все 4 конфигурации генерируются и проходят полный pipeline (lint, format, typecheck, tests, xenon)
- Никаких Jinja-артефактов (`{% %}`, `{{ }}`) в сгенерированном коде
- Все Dockerfile-ы правильно используют `python:3.12-slim`
- mypy.ini корректно рендерится с `python_version = 3.12`
- requires-python = `>=3.12` во всех pyproject.toml
- Compose-файлы структурно корректны (ошибки `docker compose config` — из-за отсутствия env vars, ожидаемое поведение)
- .env.example чистый, без лишних пустых строк (fix из iter5 сохранился)
- Lazy broker (`get_broker()`) работает корректно во всех конфигурациях
- notifications_worker корректно появляется в compose при выборе модуля
- Все предыдущие regression из iter1-5 закрыты

### Резюме

Zero functional issues. 11 находок, все косметические или документационные. Основная тема — whitespace control в Jinja-шаблонах для markdown-файлов (TASK.md, CONTRIBUTING.md, ARCHITECTURE.md). Исправление сводится к аккуратной расстановке `{%-` / `-%}` тегов в ~5 шаблонных файлах.
