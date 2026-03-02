# E2E Issues — Lazy Broker: `events.py` → `get_broker()`

Полный список проблем, обнаруженных при E2E-проверке.
Отсортировано от крупных к мелким.

Тестовые конфигурации:
- `test-e2e-standalone` — `modules=tg_bot`
- `test-e2e-fullstack` — `modules=backend,tg_bot`
- `test-e2e-backend` — `modules=backend`

Предусловие для fullstack/backend: после `make setup` нужен `make generate-from-spec`
(copier task пропускает schemas, см. issue 5).

---

## Что сделано

`events.py.j2` генерировал module-level broker:

```python
redis_url = os.getenv("REDIS_URL")
if not redis_url:
    raise RuntimeError("REDIS_URL is not set")
broker = RedisBroker(redis_url, ...)
```

Любой `import` → `RuntimeError` без env-переменной. Ломало все тесты backend/tg_bot.

**Фикс:** lazy broker через `get_broker()`:

```python
_broker: RedisBroker | None = None

def get_broker() -> RedisBroker:
    global _broker
    if _broker is None:
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            raise RuntimeError(...)
        _broker = RedisBroker(redis_url, ...)
    return _broker
```

Publishers тоже lazy — создаются при первом вызове `publish_*()`.

Обновлены потребители:
- `lifespan.py` — `from shared.generated.events import get_broker`
- `tg_bot/main.py.jinja` — `get_broker().connect()` / `get_broker().close()`
- `backend/tests/conftest.py` — mock через `events._broker = AsyncMock()`
- `backend/tests/unit/test_events.py` — `os.environ.setdefault("REDIS_URL", ...)` + `get_broker()`

---

## 1. FIXED — Тесты backend падали: `REDIS_URL is not set`

**Было:** 8 errors в backend (fullstack и backend-only).

**Стало:** 9 passed, 0 errors.

```
>> Testing backend
.........                                                                [100%]
9 passed in 0.35s
```

---

## 2. HIGH — tg_bot fullstack тесты: 5 failed, 10 errors — Pre-existing

**Pre-existing.** Не связано с lazy broker.

Все 10 errors — `patch("services.tg_bot.src.main.X")` не может resolve module path:

```
AttributeError: module 'services.tg_bot.src' has no attribute 'main'
```

**Корневая причина:** `services.tg_bot.src.main` не импортируется при `PYTHONPATH=.` из venv tg_bot, потому что `from shared.shared.http_client import ServiceClient` падает:

```
ModuleNotFoundError: No module named 'shared.shared'
```

`shared` установлен в tg_bot venv как editable package (`shared/pyproject.toml`), поэтому `shared.http_client` работает, но `shared.shared.http_client` (абсолютный путь от корня проекта) — нет.

Все 5 failures — `TestSyncUserWithBackend` — та же причина: `patch("services.tg_bot.src.main.BackendClient")` проваливается по той же схеме. Один тест дополнительно падает с `ValidationError: UserRead missing created_at, updated_at` (mock-ответ не содержит полей из сгенерированной модели).

**Замаскированная регрессия:** fixture `mock_broker` патчит `services.tg_bot.src.main.broker`, но после lazy broker в `main.py` нет module-level `broker` — есть `get_broker()`. Это сломалось бы, даже если бы import работал. Но ошибка маскируется pre-existing import failure.

**Затронуто:** только fullstack config. В standalone (modules=tg_bot, без backend) тесты не используют events/broker — 2 passed.

---

## 3. LOW — `make format` меняет файлы в свежем проекте — Pre-existing

**Pre-existing.** Не связано с lazy broker.

При первом `make format` в свежесгенерированном проекте:

| Config | Reformatted | Lint fixes |
|--------|:-----------:|:----------:|
| standalone | 3 files | 1 |
| fullstack | 2 files | 1 |
| backend | 1 file | 1 |

Format-изменения (trailing blank lines):
- `services/tg_bot/tests/unit/test_command_handler.py` — лишняя пустая строка (fullstack + standalone)
- `tests/conftest.py` — лишняя пустая строка (fullstack + standalone)
- standalone-only: ещё 1 файл (видимо standalone-версия test_command_handler)

Lint fix (одинаковый для всех):
- `.framework/framework/lib/compose_blocks.py` — I001 (unsorted imports: `import textwrap` среди `from` imports)

**Корневая причина:** template-копия `compose_blocks.py` не синхронизирована с source `framework/lib/compose_blocks.py` (source проходит lint, template-копия — нет).

---

## 4. LOW — Copier generate task пропускает schemas — Pre-existing

**Pre-existing.** Не связано с lazy broker.

Copier `_tasks` запускает `PYTHONPATH=.framework python3 -m framework.generate`, используя системный python. `datamodel-code-generator` не установлен в системе:

```
⚠ Skipping Schemas (datamodel-code-generator not installed).
  schemas.py may be stale. Run `make generate-from-spec` in Docker to regenerate.
```

После `make setup` в root venv появляется `datamodel-code-generator`, и `make generate-from-spec` работает. Но из коробки тесты backend не запускаются без ручного `make generate-from-spec`.

---

## 5. INFO — `datamodel-code-generator` FutureWarning — Pre-existing

```
FutureWarning: The default formatters (black, isort) will be replaced by ruff in a future version.
To prepare for this change, consider using: formatters=[Formatter.RUFF_FORMAT, Formatter.RUFF_CHECK].
```

Появляется при каждом вызове `make generate-from-spec`. Не влияет на работу, но засоряет вывод.

---

## 6. INFO — Copier tests all SKIPPED — Pre-existing

55 copier-тестов в `tests/copier/` все SKIPPED с `copier not installed`. Pre-existing, документировано в предыдущем E2E.

---

## Сводка

| # | Severity | Проблема | Regression? | Status |
|---|----------|----------|:---:|:---:|
| 1 | HIGH | Backend тесты: REDIS_URL not set | Да (ит. 2) | **FIXED** |
| 2 | HIGH | tg_bot fullstack: module import + mock path failures | Pre-existing* | Open |
| 3 | LOW | `make format` меняет файлы в свежем проекте | Pre-existing | Open |
| 4 | LOW | Copier generate пропускает schemas | Pre-existing | Open |
| 5 | INFO | datamodel-code-generator FutureWarning | Pre-existing | Open |
| 6 | INFO | Copier tests all SKIPPED | Pre-existing | Open |

*Issue 2 содержит замаскированную регрессию: tg_bot test fixture `mock_broker` патчит `services.tg_bot.src.main.broker`, которого больше нет (теперь `get_broker()`). Регрессия не видна из-за pre-existing import failure.

---

## Что работает

| Проверка | standalone | fullstack | backend |
|----------|:---------:|:---------:|:-------:|
| `copier copy` | OK | OK | OK |
| `make setup` | OK | OK | OK |
| `make generate-from-spec` | — | OK | OK |
| `make lint` | OK | OK | OK |
| `make format` | OK* | OK* | OK* |
| `make tests` (backend) | — | **9 passed** | **9 passed** |
| `make tests` (tg_bot) | **2 passed** | FAIL† | — |
| `make tests` (tooling) | skip | skip | skip |

*Format проходит, но первый запуск на свежем проекте меняет файлы (trailing blanks + import sort).
†Pre-existing: module import failures в tg_bot fullstack mode.
