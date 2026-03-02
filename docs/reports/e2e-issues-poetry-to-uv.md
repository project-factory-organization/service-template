
# E2E Issues — Poetry → uv Migration

Полный список проблем, обнаруженных при E2E-проверке миграции.
Отсортировано от крупных к мелким.

---

## 1. CRITICAL — `make tests` fullstack: `ModuleNotFoundError: shared.generated.schemas`

**Pre-existing.** Не связано с миграцией.

При запуске `make tests` для fullstack-проекта backend-тесты падают при импорте:

```
shared/shared/generated/events.py:13: in <module>
    from shared.generated.schemas import CommandReceived, UserRegisteredEvent
E   ModuleNotFoundError: No module named 'shared.generated.schemas'
```

`schemas.py` генерируется через `datamodel-code-generator`, который есть только в tooling-контейнере.
Copier-задача `framework.generate` при генерации проекта явно пишет:

```
⚠ Skipping Schemas (datamodel-code-generator not installed).
  schemas.py may be stale. Run `make generate-from-spec` in Docker to regenerate.
```

Но `events.py` уже сгенерирован и ссылается на `schemas.py`, которого нет.
Тесты backend'а не могут запуститься вообще.

**Вывод:** шаблон из коробки не проходит `make tests` без ручного `make generate-from-spec`.

---

## 2. HIGH — `make tests` standalone: `No tests configured for services.yml`

**Pre-existing.** Не связано с миграцией.

Standalone-проект (modules=`["tg_bot"]`) копирует tg_bot, потом copier-задача
`rm -rf services/notifications_worker` удаляет notifications_worker. Но `services.yml`
(или его парсинг в `framework.service_info`) после удаления не находит тестовых суитов
и завершается с ошибкой.

---

## 3. HIGH — `make lint`: ruff import sorting (I001) + unused imports (F401) — FIXED

**Pre-existing.** Не связано с миграцией.

Fullstack (3 ошибки):
- `services/backend/tests/conftest.py` — I001 (import block unsorted: `import tempfile` после stdlib)
- `services/tg_bot/src/main.py` — I001 (import block unsorted)
- `shared/shared/http_client.py` — I001 (import block unsorted)

Standalone (3 ошибки):
- `services/tg_bot/src/main.py` — I001
- `tests/integration/test_example.py` — F401 (`AsyncClient` imported but unused)
- `tests/integration/test_example.py` — F401 (`pytest` imported but unused)

**Фикс:** conftest.py — `import tempfile` перемещён в stdlib-блок; http_client.py — `from http`
перемещён по алфавиту; main.py.jinja — реструктурированы Jinja-блоки (stdlib alphabetical,
third-party перед first-party, `{%-`/`-%}` для whitespace); test_example.py.jinja — импорты
обёрнуты в `{% if backend %}`.

---

## 4. HIGH — `make lint`: `warning: Invalid rule code provided to # noqa: SPEC001` — FIXED

**Pre-existing.** Не связано с миграцией.

```
warning: Invalid rule code provided to `# noqa` at services/backend/src/app/api/v1/health.py:5: SPEC001
```

`SPEC001` — кастомное правило фреймворка, ruff не знает о нём и выдаёт warning.

**Фикс:** убран `# noqa: SPEC001` с `router = APIRouter()` в health.py.

---

## 5. MEDIUM — Copier warning: `DirtyLocalWarning: Dirty template changes included automatically`

**Ожидаемое поведение**, но стоит понимать.

```python
copier/_vcs.py:209: DirtyLocalWarning: Dirty template changes included automatically.
```

**Что значит:** copier работает с git-репозиторием шаблона. Когда указан `--vcs-ref HEAD`,
copier берёт последний коммит. Но если в рабочей директории есть незакоммиченные изменения
(modified, untracked файлы), copier всё равно включает их в генерацию — и предупреждает об этом.

В нашем случае мы запускали `copier copy --vcs-ref HEAD` с незакоммиченными
изменениями миграции (pyproject.toml, Dockerfiles, uv.lock и т.д.). Copier использовал
эти грязные файлы — что и нужно для тестирования. Но в CI это предупреждение не возникнет,
потому что шаблон будет чистым после коммита.

**Вывод:** при тестировании шаблона до коммита — норма. В продакшене — не должен появляться.

---

## 6. MEDIUM — Отсутствуют `.env` файлы, `docker compose` падает — FIXED

**Pre-existing.** Не связано с миграцией.

Compose-файлы ссылаются на `../.env` и `.env`:
- `infra/compose.base.yml:17` — `../.env`
- `infra/compose.tests.unit.yml:17` — `../.env`
- `infra/compose.tests.unit.yml:36` — `.env`

Copier генерирует `.env.test`, `.env.prod`, `.env.example`, но не `.env`.
Без ручного `cp infra/.env.test infra/.env && touch .env` ни `make lint`, ни `make tests` не работают.

```
env file /tmp/test-fullstack/infra/.env not found: stat /tmp/test-fullstack/infra/.env: no such file or directory
```

**Фикс:** создан `template/.env.jinja` (dev-дефолты) и `template/infra/.env.jinja`
(тестовые значения для tooling). Убран `.env` из `_exclude` в `copier.yml`,
добавлен `infra/.env` в `_skip_if_exists`. Copier теперь автоматически генерирует оба файла.

---

## 7. MEDIUM — mypy version mismatch: tooling 1.10.0 vs uv.lock 1.19.1

**Introduced by migration** (частично).

- `tooling/Dockerfile` пинит `mypy==1.10.0`
- `services/backend/pyproject.toml` имеет `mypy>=1.10.0` в dev-deps
- `uv lock` зарезолвил `mypy==1.19.1` (последняя совместимая)

Теперь в системе два mypy:
- tooling-контейнер (для `make lint` → `mypy tests`) — 1.10.0
- backend-контейнер (для `make typecheck` → `mypy .` внутри сервиса) — 1.19.1

При Poetry обе были 1.10.0, потому что Poetry уважал `^1.10.0` ceiling.
uv резолвит `>=1.10.0` в последнюю доступную.

Не баг в миграции, но расхождение версий может давать разные результаты typecheck.

---

## 8. LOW — pytest version mismatch: tooling 8.2.0 vs uv.lock 8.4.2

Аналогично mypy:
- `tooling/Dockerfile` пинит `pytest==8.2.0`
- backend dev-deps: `pytest-asyncio>=0.23.0` (тянет pytest как зависимость)
- `uv lock` зарезолвил `pytest==8.4.2`

Для pytest это менее критично, но расхождение есть.

---

## 9. LOW — Пустые строки в AGENTS.md после рендеринга Jinja — FIXED

**Pre-existing.** Не связано с миграцией.

Jinja-шаблон `AGENTS.md.jinja` при рендеринге оставляет лишние пустые строки
на месте `{% if %}` / `{% endif %}` блоков.

**Фикс:** добавлены `{%-` trim markers в AGENTS.md.jinja.

---

## 10. LOW — pip warnings в tooling/Dockerfile — FIXED

**Pre-existing.** Не связано с миграцией.

**Фикс:** добавлены `--root-user-action=ignore --disable-pip-version-check` в `pip install`.

---

## 11. INFO — backend pyproject.toml не имеет `pytest` в dev-deps — FIXED

**Pre-existing.** Обнаружено при миграции.

**Фикс:** добавлен `pytest>=8.0` в backend dev-deps, uv.lock обновлён.

---

## Сводка

| # | Severity | Проблема | Pre-existing? | Status |
|---|----------|----------|:---:|:---:|
| 1 | CRITICAL | `shared.generated.schemas` не генерируется → тесты не работают | Да | Open |
| 2 | HIGH | Standalone: "No tests configured" | Да | Open |
| 3 | HIGH | ruff I001/F401 в шаблонном коде | Да | **FIXED** |
| 4 | HIGH | `# noqa: SPEC001` warning от ruff | Да | **FIXED** |
| 5 | MEDIUM | Copier `DirtyLocalWarning` | Ожидаемо | N/A |
| 6 | MEDIUM | Нет `.env` → compose падает | Да | **FIXED** |
| 7 | MEDIUM | mypy 1.10.0 (tooling) vs 1.19.1 (uv.lock) | Частично | Open |
| 8 | LOW | pytest 8.2.0 (tooling) vs 8.4.2 (uv.lock) | Частично | Open |
| 9 | LOW | Пустые строки в AGENTS.md из-за Jinja whitespace | Да | **FIXED** |
| 10 | LOW | pip root warning + outdated pip notice | Да | **FIXED** |
| 11 | INFO | backend: `pytest` не в явных dev-deps | Да | **FIXED** |
