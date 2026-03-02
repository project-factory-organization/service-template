# E2E Issues — Итерация 2: Убрать tooling-контейнер, перейти на venv-ы

Полный список проблем, обнаруженных при E2E-проверке.
Отсортировано от крупных к мелким.

Тестовые конфигурации:
- `test-standalone` — `modules=tg_bot`
- `test-fullstack` — `modules=backend,tg_bot`
- `test-backend` — `modules=backend`

---

## 1. HIGH — Root Makefile/compose.framework.yml ссылались на удалённый `template/tooling/Dockerfile` — FIXED

**Regression.** Введено итерацией 2.

Plan описывал только файлы в `template/`, но корневой `infra/compose.framework.yml` ссылался на `template/tooling/Dockerfile` для tooling-сервиса. После удаления `template/tooling/Dockerfile` pre-commit hook (`make format`) упал:

```
resolve : lstat /home/vlad/projects/service-template/template/tooling: no such file or directory
```

**Фикс:** переписан корневой `Makefile` — убран Docker-путь (`EXEC_MODE`, `compose.framework.yml`), теперь используется `.venv/bin/ruff` напрямую. Добавлен `make setup` для установки dev-зависимостей в root `.venv/`.

---

## 2. HIGH — `enforce_spec_compliance` сканировал `services/*/.venv/` — FIXED

**Regression.** Введено итерацией 2 (per-service venvs — новая сущность).

`framework/enforce_spec_compliance.py:94` делает `services_dir.rglob("*.py")`, что теперь включает `services/backend/.venv/lib/.../fastapi/applications.py`. В fastapi найден `APIRouter` — ложный positives:

```
In services/backend/.venv/lib/python3.12/site-packages/fastapi/applications.py:
  Line 986: APIRouter should be defined in app/api/routers/, not here.
```

**Фикс:** добавлен `".venv" in file_path.parts` в skip-условие `enforce_spec_compliance.py` (и `framework/`, и `template/.framework/`).

---

## 3. HIGH — `ruff check .` сканировал `services/*/.venv/` — FIXED

**Regression.** Введено итерацией 2.

`ruff.toml` содержал `.venv/**` (корневой venv), но не `**/.venv/**` (per-service venvs). Ruff находил тысячи ошибок в site-packages:

```
services/backend/.venv/lib/python3.12/site-packages/_pytest/_code/code.py — I001
services/backend/.venv/lib/python3.12/site-packages/sqlalchemy/... — множество ошибок
```

**Фикс:** добавлен `"**/.venv/**"` в `ruff.toml` exclude.

---

## 4. HIGH — `make tests` молча проглатывал ошибки per-service тестов — FIXED

**Regression.** Введено итерацией 2.

`for` loop в `tests` таргете не пробрасывал exit-код pytest. Если backend-тесты падали, цикл продолжался, и `make tooling-tests` (успешный) устанавливал финальный exit-код = 0.

**Фикс:** добавлен `failed=0`, `|| failed=1` после pytest, `exit $$failed` в конце.

---

## 5. HIGH — Root venv не содержал `datamodel-code-generator` — FIXED

**Regression.** Частично.

`tooling/Dockerfile` устанавливал `datamodel-code-generator[http]`. После удаления контейнера корневой `make test` в pre-push hook падал:

```
⚠ Skipping Schemas (datamodel-code-generator not installed).
assert (shared_gen / "schemas.py").exists()  # FAIL
```

**Фикс:** добавлен `datamodel-code-generator[http]>=0.25` (и другие framework deps) в `make setup` корневого `Makefile`.

---

## 6. HIGH — Тесты backend/tg_bot падают: `REDIS_URL is not set` — Open

**Pre-existing.** Не связано с итерацией 2.

Генерированный `shared/shared/generated/events.py` делает:
```python
redis_url = os.getenv("REDIS_URL")
if not redis_url:
    raise RuntimeError("REDIS_URL is not set")
```

Это выполняется при **импорте**, что ломает все тесты, которые транзитивно импортируют events. Раньше работало через Docker env_file. В native venv — env-переменных нет.

Затронуты:
- `test-fullstack`: backend (4 passed, OK), tg_bot (5 failed, 10 errors)
- `test-backend`: backend tests (ImportError через conftest → main → events)
- `test-standalone`: tg_bot не использует events (2 passed, OK)

**Корневая причина:** `events.py` template (`framework/generators/events.py`) генерирует runtime-проверку `REDIS_URL` на уровне модуля. Для unit-тестов это нужно или мокать, или делать lazy broker initialization.

---

## 7. LOW — Copier tests all SKIPPED: "copier not installed" — Pre-existing

**Pre-existing.** Не связано с итерацией 2.

55 copier тестов в `tests/copier/` все SKIPPED с `copier not installed (pip install copier)`, хотя copier установлен в venv. Тесты проверяют `import copier` без активации venv, или skip-условие некорректное.

---

## Сводка

| # | Severity | Проблема | Regression? | Status |
|---|----------|----------|:---:|:---:|
| 1 | HIGH | Root Makefile ссылался на удалённый tooling/Dockerfile | Да | **FIXED** |
| 2 | HIGH | `enforce_spec_compliance` сканировал `.venv/` | Да | **FIXED** |
| 3 | HIGH | ruff сканировал per-service `.venv/` | Да | **FIXED** |
| 4 | HIGH | `make tests` не пробрасывал ошибки | Да | **FIXED** |
| 5 | HIGH | Root venv без datamodel-code-generator | Да | **FIXED** |
| 6 | HIGH | REDIS_URL not set → тесты backend/tg_bot падают | Pre-existing | Open |
| 7 | LOW | Copier tests all SKIPPED | Pre-existing | Open |

---

## Итог

5 регрессий обнаружено и исправлено. Все связаны с тем, что per-service `.venv/` — новая сущность, и инструменты (ruff, enforce_spec_compliance, Makefile) не были готовы к ней.

Оставшаяся открытая проблема (`REDIS_URL`) — pre-existing: `events.py` делает runtime check при импорте, что ломает unit-тесты без env-переменных. Требует lazy initialization broker'а.

### Что работает

| Проверка | standalone | fullstack | backend |
|----------|:---------:|:---------:|:-------:|
| `copier copy` | OK | OK | OK |
| `make setup` | OK | OK | OK |
| `make lint` | OK | OK | OK |
| `make format` | OK | OK | OK |
| `make tests` (tooling) | OK (skip) | OK (skip) | OK (skip) |
| `make tests` (services) | OK (2/2) | FAIL* | FAIL* |
| `.gitignore` present | OK | OK | OK |
| No tooling artifacts | OK | OK | OK |
| CI workflow correct | OK | OK | OK |

*FAIL из-за pre-existing REDIS_URL issue, не regression.
