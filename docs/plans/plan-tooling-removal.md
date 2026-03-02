# План: отказ от tooling-контейнера

> **Основание**: [brainstorm-tooling-removal.md](brainstorm-tooling-removal.md) — все решения приняты
> **Связан с**: [simplification-plan.md](simplification-plan.md) — пункт 4
> **Scope**: два репозитория — `service-template` и `codegen_orchestrator`
> **Status**: Итерации 1-3 DONE. Итерация 4 (orchestrator) — ожидает реализации на стороне оркестратора.

---

## Зачем

Агенты (основные пользователи фреймворка) живут в Docker. Tooling-контейнер заставлял их делать docker-in-docker для `make lint` и `make test`. Это медленно, хрупко, усложняет отладку.

Заменили Docker-based tooling на per-project venv-ы через uv. Линтеры и юнит-тесты работают плоско. Docker остаётся только для интеграционных тестов (postgres, redis) и production-деплоя.

---

## Итерация 1: Poetry → uv (service-template) — DONE ✅

**Коммит:** `0e3c3ba` (feat: migrate Poetry to uv + fix pre-existing template issues)

Заменили Poetry на uv во всех шаблонных файлах. Все `pyproject.toml` мигрированы на PEP 621, `poetry.lock` → `uv.lock`, Dockerfiles используют `COPY --from=ghcr.io/astral-sh/uv`.

### Файлы — как в плане, без отклонений

| Файл | Действие | Статус |
|------|----------|--------|
| `template/shared/pyproject.toml` | `[tool.poetry]` → `[project]` (PEP 621) | ✅ |
| `template/services/*/pyproject.toml` | `[tool.poetry]` → `[project]` + `[dependency-groups]` + `[tool.uv.sources]` | ✅ |
| `template/services/*/poetry.lock` | Удалены, заменены на `uv.lock` | ✅ |
| `template/services/*/Dockerfile` | `pip install poetry` → `COPY --from=ghcr.io/astral-sh/uv:latest`, `poetry install` → `uv pip install --system` | ✅ |
| `template/Makefile.jinja` | `poetry run pytest` → `pytest` | ✅ |

---

## Итерация 2: Venv-инфраструктура (service-template) — DONE ✅

**Коммит:** `6aaa999` (feat: remove tooling container, switch to native venv workflow)
**Доп. фиксы:** `7e7b077`, `9c2c2ba`, `dc96261`, `581cb05`

Добавили `make setup`, переписали Makefile на venv-ы, удалили tooling-контейнер и EXEC_MODE.

### Реализация vs план

| Пункт плана | Статус | Отклонения |
|-------------|--------|------------|
| `template/.framework/pyproject.toml` — создать | ✅ | — |
| `template/Makefile.jinja` — переписать | ✅ | `make setup` дополнительно включает `make generate-from-spec` (для backend) и `git config core.hooksPath .githooks` — **не было в плане**, добавлено позже для полной инициализации одной командой |
| `template/tooling/Dockerfile` — удалить | ✅ | — |
| `template/infra/compose.tests.unit.yml.jinja` — удалить | ✅ | — |
| `template/.github/workflows/ci.yml.jinja` — обновить | ✅ | — |
| `.gitignore` — добавить `.venv/` | ✅ | — |

> **Заметка для оркестратора:** `make setup` — единая точка входа после `copier copy`. Запускать **обязательно** перед любыми другими make-таргетами. Порядок: `copier copy` → `make setup` → `make lint/test/etc`. Без `make setup` не будут созданы venv-ы, не сгенерируется код из specs, не настроятся git hooks.

### `make setup` — финальная реализация

```makefile
setup:
	uv venv
	uv pip install -e .framework/ ruff xenon
	@for svc in services/*/; do \
		[ -f "$$svc/pyproject.toml" ] || continue; \
		echo ">> Setting up $$svc"; \
		(cd "$$svc" && uv sync --frozen); \
	done
	# Только для backend-конфигураций:
	@echo ">> Generating code from specs"
	$(PYTHON) -m framework.generate
	# Git hooks:
	@git config core.hooksPath .githooks 2>/dev/null || true
	@echo ">> Setup complete!"
```

> **Отклонение от плана:** План предлагал `uv pip install -e ".[dev]" -e ../../shared` для per-service venvs. Реализация использует `uv sync --frozen`, что проще и надёжнее (ставит ровно то что в lock-файле). `shared` подключается через `[tool.uv.sources]` в pyproject.toml каждого сервиса.

### Дополнительные фиксы (не были в плане)

1. **ruff exclude для `.venv/`** — `ruff check` и `ruff format` подхватывали файлы из per-service venvs. Добавлен `"**/.venv/**"` в `ruff.toml` exclude.
2. **enforce_spec_compliance skip `.venv/`** — сканер проверял файлы в venvs. Добавлен skip для `.venv` директорий.
3. **`make tests` propagation** — при ошибке одного сервиса make продолжал дальше. Добавлен `|| exit 1` для fail-fast.
4. **`ruff format --extend-exclude`** — `ruff format` не поддерживает `--extend-exclude` (только `ruff check`). Excludes перенесены в `ruff.toml`, CLI-флаги убраны.
5. **Lazy broker** — `get_broker()` вместо module-level `broker = RedisBroker(...)`. Без этого `import shared.generated.events` падал в тестах из-за отсутствия `REDIS_URL`.

---

## Итерация 3: Документация (service-template) — DONE ✅

**Коммиты:** `5c9128f`, `3eff0e6` (и промежуточные)

### Реализация vs план

| Пункт плана | Статус | Отклонения |
|-------------|--------|------------|
| `ARCHITECTURE.md.jinja` — убрать Tooling Container | ✅ | Также обновлена Directory Structure (`.framework/` вместо `templates/`), containerization strategy, и добавлены conditional blocks для standalone |
| `CONTRIBUTING.md.jinja` — заменить Docker-инструкции | ✅ | Также вычищены backend-specific секции в standalone |
| `AGENTS.md` — убрать docker-compose | ✅ | — |
| `README.md.jinja` — `make setup` как шаг 1 | ✅ | **Не было в плане** — добавлено по ходу. Quick Start теперь: (1) make setup, (2) cp .env.example .env, (3) make dev-start |

> **Заметка для оркестратора:** В сгенерированных проектах больше нет упоминаний tooling-контейнера, Poetry, EXEC_MODE. Документация описывает актуальный workflow с `make setup` и нативными venvs.

### Оставшиеся косметические проблемы

Jinja whitespace control в markdown-шаблонах не идеален — местами лишние пустые строки. Подробности в `docs/e2e-issues-iteration6.md`. Не влияет на функциональность.

---

## Итерация 4: Orchestrator (codegen_orchestrator) — TODO ⏳

**Цель**: облегчить образ агента, добавить uv cache volume.

> **Это единственная оставшаяся итерация.** Все изменения в service-template завершены.

### Файлы

| Файл | Действие |
|------|----------|
| `services/worker-manager/images/worker-base-common/Dockerfile` | Убрать pip install: ruff, xenon, pytest, pytest-cov, mypy, PyYAML, jinja2, copier. Добавить `COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv` |
| `services/worker-manager/src/worker_manager.py` (или аналог) | Добавить `"uv-cache"` volume mount + `UV_CACHE_DIR` env var при создании контейнера |
| `docker-compose.yml` | Если нужно — добавить named volume `uv-cache` |

### Что учесть при реализации

1. **`make setup` обязателен** — после `copier copy` агент ДОЛЖЕН запустить `make setup`. Это создаёт venvs, генерирует код, настраивает hooks. Без этого ничего не работает.

2. **uv cache volume** — первый `make setup` без кеша занимает ~15-30 сек (скачивание пакетов). С кешем — 3-5 сек. Shared uv-cache volume между воркерами критичен для UX.

3. **Copier нужен для scaffolder** — copier НЕ убран из шаблона (он не в шаблоне, он инструмент scaffolder'а). Scaffolder должен иметь copier установленным, worker-base — нет.

4. **Нативные инструменты** — ruff, xenon, pytest, mypy теперь устанавливаются через `make setup` в per-project venvs. Не нужны в базовом образе.

5. **Python version** — шаблон теперь генерирует проекты с `python_version` из copier (default: 3.12). Dockerfiles используют `python:{{ python_version }}-slim`. Worker-base образ должен иметь совместимый Python.

### Тестирование

```bash
# 1. Билд worker-base образов
docker build -f services/worker-manager/images/worker-base-common/Dockerfile .

# 2. Проверить что uv доступен в контейнере
docker run --rm worker-base-common uv --version

# 3. Проверить что убранные инструменты НЕ доступны глобально
docker run --rm worker-base-common ruff --version    # должен упасть
docker run --rm worker-base-common pytest --version   # должен упасть

# 4. E2E: полный цикл
# scaffolder создаёт проект → developer agent клонирует → make setup (из uv cache) → make lint → make test → push
# Первый прогон: ~20-35 сек (скачивание)
# Второй прогон (другой worker, тот же cache volume): ~3-5 сек
```

**Критерий закрытия**: worker-base образ легче. Агент может `make setup && make lint && make test` без предустановленных Python-пакетов. uv cache шарится между воркерами.

---

## Сводка изменений по репозиториям

### service-template (итерации 1-3) — DONE ✅

| Действие | Файлы |
|----------|-------|
| **Удалены** | `template/tooling/Dockerfile`, `template/infra/compose.tests.unit.yml.jinja`, `template/services/*/poetry.lock` |
| **Созданы** | `template/.framework/pyproject.toml` |
| **Переписаны** | `template/Makefile.jinja`, `template/.github/workflows/ci.yml.jinja` |
| **Мигрированы** | `template/shared/pyproject.toml`, `template/services/*/pyproject.toml`, `template/services/*/Dockerfile` |
| **Обновлена документация** | `ARCHITECTURE.md.jinja`, `CONTRIBUTING.md.jinja`, `README.md.jinja`, `AGENTS.md`, `TASK.md.jinja` |

### codegen_orchestrator (итерация 4) — TODO ⏳

| Действие | Файлы |
|----------|-------|
| **Переписать** | `services/worker-manager/images/worker-base-common/Dockerfile` |
| **Обновить** | `services/worker-manager/src/` — volume mount + env var |
