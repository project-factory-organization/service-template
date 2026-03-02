# AGENTS — Backend API

## Location

- Код, тесты и зависимости живут в `services/backend`. Не разносите `Dockerfile`, `src/` или `tests/` по другим каталогам.
- Любые команды запускайте через `make` и docker-compose (см. `CONTRIBUTING.md`). Локальный Python не используем.

## Spec-First Workflow

Backend использует spec-first подход: модели и протоколы генерируются из YAML-спецификаций.

**Расположение спеков:**
- `shared/spec/models.yaml` — общие Pydantic-модели (схемы данных)
- `services/backend/spec/*.yaml` — domain operations (REST endpoints + events)

**Workflow:**
1. Отредактируйте спек (`shared/spec/models.yaml` или `services/backend/spec/<domain>.yaml`)
2. Запустите `make validate-specs` (проверяет YAML до генерации)
3. Запустите `make generate-from-spec`
4. Сгенерированные протоколы появятся в `services/backend/src/generated/protocols.py`
5. Реализуйте методы в `services/backend/src/controllers/<domain>.py`

**Правило:** Никогда не создавайте `BaseModel` вручную — схемы генерируются из `models.yaml`. Роутеры (`APIRouter`) пишутся вручную (см. раздел «Роутеры» ниже).

## Directory Structure

```
services/backend/
├── spec/              # YAML спецификации (Source of Truth)
├── src/
│   ├── app/           # Бизнес-логика: repositories, models, lifespan
│   ├── controllers/   # Реализации протоколов (ваш код)
│   └── generated/     # НЕ РЕДАКТИРОВАТЬ: protocols.py, routers
├── migrations/        # Alembic миграции
└── tests/
```

## Роутеры

Роутеры пишутся вручную в `src/app/api/routers/<domain>.py` и подключаются в `src/app/api/router.py`.

**Пример спека с list-операцией** (`spec/todos.yaml`):
```yaml
domain: todos
config:
  rest:
    prefix: "/todos"
    tags: ["todos"]

operations:
  list_todos:
    output: list[TodoRead]       # list[Model] для коллекций
    rest:
      method: GET
      path: ""

  create_todo:
    input: TodoCreate
    output: TodoRead
    rest:
      method: POST
      path: ""
      status: 201

  update_todo:
    input: TodoUpdate            # PATCH для partial updates
    output: TodoRead
    params:
      - name: todo_id
        type: int
    rest:
      method: PATCH
      path: "/{todo_id}"
```

**Пример роутера** (`src/app/api/routers/todos.py`):
```python
"""Router for todos."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from services.backend.src.controllers.todos import TodosController
from services.backend.src.core.db import get_async_db
from services.backend.src.generated.protocols import TodosControllerProtocol
from shared.generated.schemas import TodoCreate, TodoRead, TodoUpdate

router = APIRouter(prefix="/todos", tags=["todos"])


def get_controller() -> TodosControllerProtocol:
    return TodosController()


@router.get("", response_model=list[TodoRead])
async def list_todos(
    session: AsyncSession = Depends(get_async_db),  # noqa: B008
    controller: TodosControllerProtocol = Depends(get_controller),  # noqa: B008
) -> list[TodoRead]:
    return await controller.list_todos(session=session)


@router.post("", response_model=TodoRead, status_code=201)
async def create_todo(
    payload: TodoCreate = Body(...),  # noqa: B008
    session: AsyncSession = Depends(get_async_db),  # noqa: B008
    controller: TodosControllerProtocol = Depends(get_controller),  # noqa: B008
) -> TodoRead:
    return await controller.create_todo(session=session, payload=payload)


@router.patch("/{todo_id}", response_model=TodoRead)
async def update_todo(
    todo_id: int = Path(...),  # noqa: B008
    payload: TodoUpdate = Body(...),  # noqa: B008
    session: AsyncSession = Depends(get_async_db),  # noqa: B008
    controller: TodosControllerProtocol = Depends(get_controller),  # noqa: B008
) -> TodoRead:
    return await controller.update_todo(session=session, todo_id=todo_id, payload=payload)
```

**Подключение в `src/app/api/router.py`:**
```python
from .routers.todos import router as todos_router

api_router.include_router(todos_router)
```

## Database & Migrations

- Миграции в `services/backend/migrations/versions/`.
- Перед запуском API: `services/backend/scripts/migrate.sh`.
- Создать новую миграцию: `make makemigrations name="describe_change"`.

## Event Publishing

Backend подключается к Redis через lazy broker в lifespan:

```python
from shared.generated.events import get_broker

@asynccontextmanager
async def lifespan(app: FastAPI):
    broker = get_broker()
    await broker.connect()
    yield
    await broker.close()
```

Публикация событий из контроллеров:
```python
from shared.generated.events import publish_user_registered
await publish_user_registered(event)
```

## Key Commands

| Команда | Назначение |
|---------|-----------|
| `make generate-from-spec` | Перегенерировать код из спеков |
| `make validate-specs` | Проверить YAML спеки |
| `make lint-specs` | Проверить соответствие спекам |
| `make lint-controllers` | Проверить синхронизацию контроллеров с протоколами |
| `make makemigrations name="..."` | Создать Alembic миграцию |
| `make openapi` | Экспорт OpenAPI JSON |
| `make tests backend` | Запустить тесты backend |
