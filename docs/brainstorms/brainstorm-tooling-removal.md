# Пункт 4: Отказ от tooling-контейнера

> **Статус**: брейншторм / обсуждение
> **Связан с**: [simplification-plan.md](simplification-plan.md) — пункт 4
> **Контекст**: агенты (основные пользователи фреймворка) живут в Docker. Docker-in-Docker — боль. Нужна плоская структура для локальной разработки.

---

## Установка

Фреймворком в первую очередь пользуются **агенты**, а не люди. Агенты живут в Docker-контейнерах. Чтобы не городить docker-in-docker, dev-инструменты (линтеры, тесты) должны запускаться плоско — без контейнеров.

Интеграционные тесты без Docker скорее всего не обойдутся (postgres, redis), но линтеры и юнит-тесты должны работать нативно без проблем.

**Важно**: меняем только то, что идёт в **сгенерированные проекты**. Фреймворк (`/Makefile`, `/infra/compose.framework.yml`) пока не трогаем.

---

## Решённые вопросы

### ✅ 1. Poetry → uv: мигрируем

**Решение**: мигрируем pyproject.toml на PEP 621 + uv.

**Сложность: низкая.** Механическая миграция:

| Что | Объём | Суть |
|-----|-------|------|
| pyproject.toml | 4 файла (shared, backend, tg_bot, notifications_worker) | `[tool.poetry]` → `[project]` (PEP 621) + `[tool.uv.sources]` для shared editable |
| Lock-файлы | 3 файла | Удалить poetry.lock, `uv lock` создаст uv.lock |
| Dockerfiles сервисов | 3 файла | `pip install poetry` → `COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv` + `uv pip install --system` |
| Makefile.jinja | 2 строки | `poetry run pytest` → `.venv/bin/pytest` |
| CI workflow | ~0 | CI ходит через Docker, Dockerfiles внутри уже будут с uv |

**Побочные эффекты — только положительные:**
- Docker build быстрее (uv = один бинарник vs `pip install poetry`)
- Стандартный формат PEP 621 (нет vendor lock)
- Готовность к отказу от tooling-контейнера

Пример миграции pyproject.toml (backend):

```toml
# БЫЛО (Poetry)
[tool.poetry]
name = "backend"
version = "0.1.0"
package-mode = false

[tool.poetry.dependencies]
python = "^3.11"
fastapi = ">=0.110.0,<1.0.0"
shared = {path = "../../shared", develop = true}

[tool.poetry.group.dev.dependencies]
mypy = "^1.10.0"

# СТАЛО (PEP 621 + uv)
[project]
name = "backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110.0,<1.0.0",
    "shared",
]

[dependency-groups]
dev = ["mypy>=1.10.0"]

[tool.uv.sources]
shared = { path = "../../shared", editable = true }
```

Пример миграции Dockerfile:

```dockerfile
# БЫЛО
RUN pip install --no-cache-dir poetry
COPY services/backend/pyproject.toml services/backend/poetry.lock ./services/backend/
RUN cd services/backend \
    && poetry config virtualenvs.create false \
    && poetry install --without dev --no-root

# СТАЛО
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY services/backend/pyproject.toml services/backend/uv.lock ./services/backend/
RUN cd services/backend \
    && uv pip install --system --no-cache .
```

---

### ✅ 2. Полная изоляция через venv-ы (не зависим от образа агента)

**Решение**: вариант B — проект полностью самодостаточный. Все dev-инструменты ставятся через `make setup` в venv-ы проекта, а не предустанавливаются в Docker-образе агента.

**Аргументы за:**
- Проект работает в любом окружении (образ агента, локально у человека, в CI)
- Образ агента становится легче (~200-300MB меньше)
- С uv cache дублирование не стоит ничего по времени
- Правильная модель: проект без setup не готов, как `npm install` в JS

**Целевая структура venv-ов после `make setup`:**

```
project/
├── .venv/                          ← root "tooling" venv
│   └── ruff, pydantic, PyYAML, jinja2, datamodel-codegen, pytest (для tooling-тестов)
├── .framework/                     ← код фреймворка
├── shared/
├── services/
│   ├── backend/
│   │   └── .venv/                  ← fastapi, sqlalchemy, shared (editable), pytest
│   └── tg_bot/
│       └── .venv/                  ← python-telegram-bot, shared (editable), pytest
```

Per-service venv-ы нужны чтобы при 10 микросервисах не словить конфликты зависимостей.

---

### ✅ 3. Трёхслойная архитектура: образ / кэш / setup

**Решение**: разделение на три слоя.

#### Слой 1: Worker base image (предустановлено, минимум)

| Остаётся | Убираем |
|----------|---------|
| Python 3.12 | ~~ruff~~ |
| uv (один бинарник) | ~~xenon~~ |
| git, make, curl, jq | ~~pytest, pytest-cov~~ |
| Claude Code, ripgrep | ~~mypy~~ |
| | ~~pydantic, PyYAML, jinja2~~ |
| | ~~datamodel-codegen~~ |
| | ~~poetry~~ |
| | ~~copier~~ |

Образ становится значительно легче и быстрее пуллится.

#### Слой 2: uv cache volume (шарится между воркерами)

Именованный Docker volume, монтируется в каждый worker container:

```python
# worker-manager: при создании контейнера
volumes = {
    workspace_dir: {"bind": "/workspace", "mode": "rw"},
    "uv-cache": {"bind": "/home/worker/.cache/uv", "mode": "rw"},  # NEW
}
```

uv cache хранит **скачанные wheels** (архивы пакетов). Экономит сеть, не экономит распаковку:

| Этап | Без кэша | С кэшем |
|------|----------|---------|
| Скачивание с PyPI | ~15-30 сек | 0 |
| Создание venv + установка | ~3-5 сек | ~3-5 сек |
| **Итого `make setup`** | ~20-35 сек | **~3-5 сек** |

Это **одна строка в worker-manager** + `UV_CACHE_DIR` в env контейнера.

#### Слой 3: `make setup` (per-project, запускается агентом)

```makefile
setup:
	uv venv && uv pip install <tooling deps>          # root .venv
	cd services/backend && uv venv && uv pip install -e ".[dev]" -e ../../shared
	cd services/tg_bot && uv venv && uv pip install -e ".[dev]" -e ../../shared
```

---

### ✅ 4. Copier не нужен агенту-разработчику

**Решение**: copier убираем из worker-base образа.

Единственный use-case — добавить модуль (backend к standalone боту). Но это отдельная итерация LangGraph → scaffolder-сервис делает `copier update`. Агент-разработчик не должен сам вызывать copier.

Copier остаётся только в scaffolder-сервисе.

---

### ✅ 5. Scaffolder не запускает `make setup`

**Решение**: scaffolder только генерирует и пушит. `make setup` — ответственность агента-разработчика.

Workflow:
```
scaffolder: copier copy → git push → done
developer:  git clone → make setup → работает → make lint → make test → push
CI:         xenon, integration tests, build & push
```

`make setup` — первая команда агента после clone. Прописываем в CLAUDE.md / CONTRIBUTING.md генерируемого проекта.

---

### ✅ 6. .framework/ — editable install

**Решение**: ставим `.framework/` как editable пакет в root `.venv/`.

Добавляем `.framework/pyproject.toml`:

```toml
[project]
name = "framework"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.5",
    "PyYAML>=6.0",
    "jinja2>=3.0",
    "datamodel-code-generator[http]",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

В `make setup`:

```makefile
setup:
	uv venv
	uv pip install -e .framework/ ruff    # framework (с его deps) + ruff
	# ... per-service venvs
```

**Аргументы за (vs PYTHONPATH):**
- `import framework` работает без переменных окружения — `.venv/bin/python -m framework.generate` и всё
- IDE резолвит импорты, автокомплит работает
- **Единый source of truth** для зависимостей фреймворка — сейчас они в `tooling/Dockerfile` который удаляем, переезжают в `.framework/pyproject.toml`
- Консистентно с тем, как shared ставится editable в сервисные venv-ы
- Editable = изменения в `.framework/` подхватываются мгновенно

**Стоимость**: один файл ~10 строк.

**Структура venv-ов обновлённая:**

```
project/
├── .venv/                          ← root "tooling" venv
│   └── framework (editable), ruff, pytest
│       framework тянет: pydantic, PyYAML, jinja2, datamodel-codegen
├── .framework/                     ← код фреймворка + pyproject.toml
├── services/
│   ├── backend/.venv/              ← fastapi, sqlalchemy, shared (editable), pytest
│   └── tg_bot/.venv/               ← python-telegram-bot, shared (editable), pytest
```

---

### ✅ 7. xenon и mypy — оставляем локально

**Решение**: оба инструмента доступны разработчику. Лишняя итерация CI дороже чем пара пакетов.

**xenon** → root `.venv/` (рядом с ruff). Проверяет complexity всего проекта, не привязан к сервису.

**mypy** → per-service `.venv/` (уже есть в `[dependency-groups] dev` каждого сервиса). mypy должен видеть все зависимости проверяемого кода (fastapi, sqlalchemy и т.д.) — поэтому per-service, а не глобальный.

**Стоимость**: +1 слово `xenon` в `make setup` для root venv. mypy — бесплатно, уже в dev deps.

**CI-only остаются:**
- Интеграционные тесты (нужен postgres, redis)
- build & push images

**Итоговый `make setup`:**

```makefile
setup:
	uv venv
	uv pip install -e .framework/ ruff xenon    # root tooling venv
	cd services/backend && uv venv && uv pip install -e ".[dev]" -e ../../shared
	cd services/tg_bot && uv venv && uv pip install -e ".[dev]" -e ../../shared
```

**Итоговая структура:**

```
project/
├── .venv/                          ← root tooling venv
│   └── framework (editable), ruff, xenon, pytest
│       framework тянет: pydantic, PyYAML, jinja2, datamodel-codegen
├── .framework/                     ← код фреймворка + pyproject.toml
├── services/
│   ├── backend/.venv/              ← fastapi, sqlalchemy, shared (editable), pytest, mypy
│   └── tg_bot/.venv/               ← python-telegram-bot, shared (editable), pytest, mypy
```

---

### ✅ 8. compose.tests.unit.yml — удаляем целиком

**Решение**: файл `template/infra/compose.tests.unit.yml.jinja` удаляется.

Он содержал два сервиса:
- **tooling** — убираем (вся суть пункта 4)
- **backend-tests-unit** — больше не нужен: юнит-тесты backend бегут нативно через `services/backend/.venv/bin/pytest tests/unit` с SQLite in-memory

Остаётся только `compose.tests.integration.yml` — полный стек (postgres, redis). Это CI-only.

---

## Открытые вопросы

### ✅ 9. Spec-проверки — решено editable install-ом

`enforce_spec_compliance`, `validate_specs_cli`, `lint_controllers_cli` — Python из `.framework/`. Запускаются из root `.venv/`: `.venv/bin/python -m framework.enforce_spec_compliance`. pydantic и PyYAML приходят как зависимости framework пакета. Вопрос закрыт.

---

### ✅ 10. EXEC_MODE — удаляем

**Решение**: EXEC_MODE удаляется. Makefile становится однопутным — всё через venv-ы.

Сейчас `EXEC_MODE ?= docker` переключает два пути (native / docker compose run tooling). Docker-путь исчезает вместе с tooling-контейнером → остаётся один путь → абстракция не нужна.

**CI тоже переходит на native:**

```yaml
# ci.yml.jinja
- uses: astral-sh/setup-uv@v4
- run: make setup
- run: make lint           # native, через .venv/
- run: make test           # native, per-service .venv/
```

Интеграционные тесты — отдельный таргет `make test-integration`, явно через docker compose (compose.tests.integration.yml). Единственное место где Docker остаётся в dev-workflow.

---

## Открытые вопросы

Нет открытых вопросов. Все решения приняты. План реализации: [plan-tooling-removal.md](plan-tooling-removal.md)
