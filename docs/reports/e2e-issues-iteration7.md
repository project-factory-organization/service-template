# E2E Issues — Iteration 7

**Date:** 2026-03-01
**Commit:** `44a17d8` (test: rewrite and re-enable copier tests)
**Copier:** 9.11.0 | **Python:** 3.12.3 | **uv:** 0.10.4 | **Ruff:** 0.15.4 | **Docker:** 29.2.1

## Test Matrix

| Stage                      | backend | standalone | fullstack | full |
|----------------------------|---------|------------|-----------|------|
| copier copy                | OK      | OK         | OK        | OK   |
| file structure             | OK      | OK         | OK        | OK   |
| no Jinja artifacts         | OK      | OK         | OK        | OK   |
| .env.example               | OK      | OK         | OK        | OK   |
| services.yml               | OK      | OK         | OK        | OK   |
| make setup                 | OK      | OK         | OK        | OK   |
| make lint                  | OK      | OK         | OK        | OK   |
| make format                | OK      | OK         | OK        | OK   |
| make typecheck (mypy)      | OK      | OK         | OK        | OK   |
| make tests (unit)          | OK (9p) | OK (2p)    | OK (24p)  | OK (28p) |
| make generate-from-spec    | OK      | n/a        | OK        | OK   |
| compose.base.yml config    | OK      | OK         | OK        | OK   |
| compose.dev.yml config     | OK      | OK         | OK        | OK   |
| compose.prod.yml config    | OK      | OK         | OK        | **FAIL** |
| compose.tests.int config   | OK      | OK         | OK        | OK   |
| Docker build (clean)       | OK      | OK         | OK        | OK   |
| Docker build (after setup) | **FAIL**| **FAIL**   | **FAIL**  | **FAIL** |
| compose.base.yml up        | **FAIL**| n/t        | OK        | n/t  |
| compose.dev.yml up         | **FAIL**| **FAIL**   | n/t       | n/t  |
| health endpoint            | —       | n/a        | OK        | —    |
| CRUD API                   | —       | n/a        | OK        | —    |
| CI workflow                | OK      | OK         | OK        | OK   |
| deploy.yml                 | OK      | OK         | OK        | OK   |

n/t = not tested (blocked by earlier failure), n/a = not applicable

---

## #1 — ~~Нет .dockerignore: host .venv ломает Docker build~~ → ✅ FIXED

**Severity:** HIGH (Docker образы нерабочие после `make setup`)
**Affected:** backend, standalone, fullstack, full
**File:** template/.dockerignore (добавлен, 14 строк)

Шаблон не генерирует `.dockerignore`. После `make setup` создаются `services/*/.venv/` на хосте. При `docker build` шаг `COPY services/backend ./services/backend` копирует HOST `.venv` поверх Docker-built `.venv`, заменяя корректные шебанги (`#!/app/services/backend/.venv/bin/python`) на хостовые (`#!/tmp/.../python`).

**Пример:**
```
# Docker-built (корректный):
#!/app/services/backend/.venv/bin/python

# Host-contaminated (сломанный):
#!/tmp/e2e-test/backend/services/backend/.venv/bin/python
```

Контейнер при запуске:
```
/app/services/backend/.venv/bin/alembic: cannot execute: required file not found
```

**Воспроизведение:** `make setup && docker build -f services/backend/Dockerfile .`
**Workaround:** `rm -rf services/*/.venv && docker build ...`

**Fix:** Добавить `.dockerignore` в шаблон:
```
.venv/
services/*/.venv/
.framework/
__pycache__/
*.pyc
.git/
.env
.env.local
*.egg-info/
.mypy_cache/
.ruff_cache/
.pytest_cache/
.coverage
```

---

## #2 — ~~compose.dev.yml: `bash -lc` сбрасывает Docker PATH~~ → ✅ FIXED

**Severity:** HIGH (dev mode полностью нерабочий для backend)
**Affected:** backend, fullstack, full
**File:** template/infra/compose.dev.yml.jinja (исправлено: `bash -c` без `-l`)

`compose.dev.yml` использует `bash -lc "..."` для запуска backend. Флаг `-l` (login shell) подгружает `/etc/profile` из base image (`python:3.12-slim`), который перезаписывает `PATH`:

```
# Dockerfile ENV:
PATH=/app/services/backend/.venv/bin:/usr/local/bin:...

# После bash -l:
PATH=/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games
```

Результат: `alembic: command not found`, `uvicorn: command not found`.

**Fix:** Убрать `-l` флаг:
```yaml
command: >-
  bash -c "./services/backend/scripts/migrate.sh &&
  uvicorn services.backend.src.main:app --host 0.0.0.0 --port 8000 --reload"
```

---

## #3 — ~~backend-only: lifespan требует REDIS_URL~~ → ✅ FIXED

**Severity:** HIGH (backend-only не стартует в Docker)
**Affected:** backend
**File:** template/services/backend/src/app/lifespan.py.jinja (исправлено: broker условен по `modules`)

При `modules=backend` (без tg_bot/notifications) lifespan.py безусловно вызывает `get_broker()`, который требует `REDIS_URL`. Но `.env.example` для backend-only корректно не включает `REDIS_URL` (Redis не нужен).

```python
# lifespan.py — всегда вызывает broker
broker = get_broker()  # RuntimeError: REDIS_URL is not set
await broker.connect()
```

```
RuntimeError: REDIS_URL is not set; please add it to your environment variables
ERROR:    Application startup failed. Exiting.
```

**Fix:** Обернуть в условие или генерировать broker-код только при наличии tg_bot/notifications:
```python
{% if 'tg_bot' in modules_list or 'notifications' in modules_list %}
broker = get_broker()
await broker.connect()
{% endif %}
```

---

## #4 — compose.prod.yml: frontend extends несуществующий сервис

**Severity:** MEDIUM (prod deploy сломан для full)
**Affected:** full
**File:** template/infra/compose.prod.yml.jinja

`compose.prod.yml` содержит `frontend: extends: compose.base.yml: frontend`, но `compose.base.yml` не содержит `frontend` сервис. `services.yml` для frontend говорит "served separately via infra/compose.frontend.yml", но такого файла нет.

```
$ docker compose -f compose.base.yml -f compose.prod.yml config
cannot extend service "frontend": service "frontend" not found in compose.base.yml
```

**Fix:** Либо добавить frontend в compose.base.yml, либо условно исключить frontend из compose.prod.yml, либо создать отдельный compose.frontend.yml.

---

## #5 — Integration test: health endpoint asserts "healthy" vs actual "ok"

**Severity:** MEDIUM (интеграционные тесты упадут)
**Affected:** backend, fullstack, full
**File:** template/tests/integration/test_example.py.jinja

```python
# test_example.py:
assert data["status"] == "healthy"

# Реальный health endpoint:
return {"status": "ok"}
```

**Fix:** Привести в соответствие — либо endpoint возвращает `"healthy"`, либо тест ассертит `"ok"`.

---

## #6 — compose.dev.yml не устанавливает PATH для host venv

**Severity:** MEDIUM (dev mode не находит site-packages для tg_bot/notifications)
**Affected:** standalone, fullstack, full (tg_bot, notifications_worker)
**File:** template/infra/compose.dev.yml.jinja

В dev mode (`volumes: ../:/workspace:delegated`), `PYTHONPATH=/workspace` устанавливается, но PATH не включает хостовой `.venv/bin/`. Сервисы типа tg_bot (CMD: `python services/tg_bot/src/main.py`) используют python из Docker PATH (`/app/services/tg_bot/.venv/bin/python`), но этот python не находит модули, установленные в хостовом venv.

```
ModuleNotFoundError: No module named 'telegram'
```

Связано с #1 (host .venv) и #2 (PATH), но даже с .dockerignore dev mode mount перезаписывает /workspace.

**Fix:** В compose.dev.yml добавить environment или entrypoint, активирующий хостовой venv:
```yaml
environment:
  PATH: /workspace/services/tg_bot/.venv/bin:${PATH}
```
Или перейти на `uv run` в dev mode.

---

## #7 — Standalone CI workflow: лишний Clean up step

**Severity:** LOW (безвредный no-op)
**Affected:** standalone
**File:** template/.github/workflows/ci.yml.jinja

Standalone CI (без backend) содержит шаг `Clean up` с `docker compose -f infra/compose.tests.integration.yml down`, но `compose.tests.integration.yml` содержит `services: {}`. No-op, но мусорный шаг.

**Fix:** Условно генерировать Clean up только при наличии backend.

---

## #8 — services.yml: пустые строки в conditional секциях

**Severity:** INFO (косметика)
**Affected:** standalone, fullstack

```yaml
# standalone services.yml:
services:

  - name: tg_bot        # ← пустая строка перед первым сервисом
```

```yaml
# fullstack services.yml:
services:

  - name: backend       # ← пустая строка перед backend
```

Jinja `{% if %}` блоки оставляют пустые строки при false-ветках.

**Fix:** Использовать `{%- if -%}` с trim в шаблоне services.yml.

---

## Итого

| Severity | Count | Issues | Status |
|----------|-------|--------|--------|
| HIGH     | 3     | #1, #2, #3 | ✅ Все исправлены |
| MEDIUM   | 3     | #4, #5, #6 | #4 условно исправлен, #5 и #6 открыты |
| LOW      | 1     | #7 | Открыт |
| INFO     | 1     | #8 | Открыт |

---

## Что работает хорошо

- Copier copy: все 4 конфигурации генерируются без ошибок, no Jinja artifacts
- `make setup` проходит для всех конфигов, venvs корректные
- `make lint` (ruff + xenon + spec validation + controller sync) — чисто для всех
- `make format` — все файлы уже форматированы (0 changes)
- `make typecheck` (mypy) — success для всех сервисов
- Unit тесты: 63 теста проходят суммарно (backend:9, tg_bot:2/15, notifications:4)
- `make generate-from-spec` — корректная кодогенерация для всех конфигов с backend
- Docker Compose config validation: base, dev, integration — валидны для всех
- Docker build (на чистом контексте без host .venv) — успешен для всех сервисов
- Fullstack stack (compose.base.yml): backend + db + redis стартуют, миграции проходят, API работает, CRUD функционирует
- tg_bot в fullstack: запускается, подключается к Redis, крутит polling loop
- CI/deploy workflows: корректно генерируются с правильной matrix для всех конфигов
- Module exclusion: standalone корректно исключает backend, shared/spec, migrations
- .env.example: корректный набор переменных для каждой конфигурации

---

## Резюме

Шаблон в хорошей форме для статических проверок (lint, typecheck, unit tests, codegen).

**Исправлено после первоначального аудита:**
1. ~~**Критическое:** `.dockerignore`~~ → ✅ Добавлен `template/.dockerignore`
2. ~~**Критическое:** `bash -lc`~~ → ✅ Исправлено на `bash -c`
3. ~~**Критическое:** REDIS_URL~~ → ✅ Broker условен по `modules`

**Остаётся открытым:**
4. **Среднее:** frontend не в compose.base.yml, prod deploy сломан для full config
5. **Среднее:** Integration test assert `"healthy"` vs `"ok"`
6. **Среднее:** compose.dev.yml PATH не включает per-service `.venv/bin` (добавлено в backlog)
