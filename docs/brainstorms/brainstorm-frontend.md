# Frontend и кодогенерация: решения

## Контекст

Бэкенд выстроен по принципу spec-first с генераторами и единообразными хэндлерами. Фронтенд — пустая коробка (Astro + React, в `src` только `.gitkeep`). При добавлении новой сущности агент вручную пишет роутер, request/response схемы и подключение — 80-150 строк бойлерплейта каждый раз. Нужно определить, как развивать фронтенд-модуль и сократить рутину в рамках философии проекта ("Rigidity is Freedom", "Spec-First", "Batteries Included").

---

## Принятые решения: Frontend

### 1. Astro + React (file-based routing)

Astro остаётся основой. Структура `src/pages/` определяет маршруты автоматически. React-компоненты встраиваются как islands с директивами гидратации (`client:load`, `client:idle`).

**Отвергнуто:** генерация маршрутов из YAML-спеки — добавляет сложность, создаёт жёсткую связь фронт↔бэкенд, требует свой генератор. File-based routing решает задачу нативно без оверхеда.

### 2. Refine для админки

Вместо ручного написания CRUD-компонентов используем [Refine](https://refine.dev/) — headless-first фреймворк для админок и CRUD-приложений. Встраивается в Astro как island через catch-all роут `src/pages/admin/[...slug].astro` с `client:only="react"`.

**Почему Refine:**
- **Headless + shadcn/ui нативно** — официальная интеграция через shadcn registry. Визуальное единообразие с остальным фронтом без кастомного темирования.
- **Лёгкий** — ядро `@refinedev/core` ~57 KB gzip (vs ~316 KB у React-admin с Material UI).
- **Простой интерфейс для кодогенерации** — dataProvider: 5 обязательных методов (`getList`, `getOne`, `create`, `update`, `deleteOne`). Проще генерировать из YAML-спек.
- **Pluggable router** — абстрактный `routerProvider` (4 метода), не привязан к react-router жёстко.
- **Всё бесплатно** — MIT без Enterprise paywall (RBAC, audit log и т.д.).

Из спеки генерируется `dataProvider` (маппинг операций на REST endpoints) и список ресурсов. `authProvider` подключается к нашему auth-слою — единый JWT, единая сессия с юзерскими страницами.

**Альтернативы:**
- **React-admin** — зрелее (10+ лет, ~142K npm downloads/week), богаче экосистема (50+ коннекторов), продвинутые оптимизации (optimistic updates, query aggregation). Но: тяжелее, Material UI по умолчанию (shadcn только через отдельный [shadcn-admin-kit](https://github.com/marmelab/shadcn-admin-kit), <1 года), RBAC/audit за платной лицензией.
- **Свой генератор** CRUD-компонентов из `models.yaml` — полный контроль, но большой объём работы на старте.

### 3. Авторизация из коробки, параметризуемая через Copier

Три уровня доступа: **Public** → **User** → **Admin**. Каркас включает `AuthContext`, `<ProtectedRoute>`, страницу логина, автоматическую подшивку Bearer-токена в API-клиенте.

**Токены: access в памяти, refresh в httpOnly cookie.**

Бэкенд (scaffold-эндпоинты):
- `POST /auth/login` → возвращает `{ access_token }` + ставит httpOnly cookie с refresh token
- `POST /auth/refresh` → читает cookie, возвращает новый `{ access_token }` + ротирует cookie
- `POST /auth/logout` → удаляет cookie

Фронтенд (scaffold):
- `apiClient.ts` — interceptor: при 401 автоматически дёргает `/auth/refresh`, повторяет запрос с новым access token. Promise-lock предотвращает множественные refresh при параллельных запросах.
- `AuthContext` — хранит access token в стейте (не в localStorage). При mount вызывает `/auth/refresh` для восстановления сессии после перезагрузки страницы.

**Почему этот подход:**
- Refresh token недоступен из JS → XSS не может его украсть (безопаснее localStorage)
- Не нужен CSRF-токен (access передаётся в Authorization header, не в cookie)
- Interceptor прозрачен — компоненты и хуки не знают про refresh
- Легко кастомизировать: заменить cookie на localStorage — 2 функции, добавить OAuth — заменить `/auth/login` на redirect flow

Параметризация через `copier.yml` (флаг `frontend_auth: bool`):
- `true` — полная структура: три роли, refresh flow, защищённые роуты, страница логина.
- `false` — лендинг-режим: только публичные страницы, API-клиент без токенов.

**Обоснование:** агенты плохо справляются с ручным добавлением/удалением auth-слоя — ломают импорты, забывают провайдеры. Параметризация на этапе scaffolding исключает эту проблему.

### 4. TypeScript-типы через OpenAPI (без генерации хуков)

Генерация TypeScript-интерфейсов из OpenAPI-схемы, которую FastAPI генерит автоматически из зарегистрированных роутеров и Pydantic-схем. Один источник правды — поднятый бэкенд.

Цепочка:
```
make dev-start → FastAPI поднимается
    → app.openapi() → openapi.json
    → openapi-typescript → frontend/src/generated/types.ts
    → /docs → Swagger UI (документация API бесплатно)
```

**Почему через OpenAPI, а не свой генератор:**
- OpenAPI из FastAPI уже есть бесплатно — не нужно писать маппинг типов
- Отражает реальные кастомизированные Python-схемы (не исходный YAML)
- `openapi-typescript` — зрелый тул (5K+ stars), не нужно поддерживать свой
- Swagger UI — документация API из коробки для каждого проекта
- Валидация в моменте: если схема сломана, стек не поднимется → агент получает обратную связь

**Trade-off:** требуется поднятый бэкенд для генерации TS-типов. Это приемлемо — в процессе разработки стек поднимается через `make dev-start`. Для фронтенд-разработчиков без Python — `openapi.json` коммитится в репозиторий.

**Что НЕ генерируется:** React Query хуки на каждую операцию — YAGNI. Юзерские страницы используют 5-10 точечных вызовов, а не полный CRUD. Refine dataProvider покрывает админку, остальное пишется вручную с типобезопасностью от сгенерированных интерфейсов.

Базовый `apiClient` (fetch-обёртка с auth, base URL, error handling) — в scaffold-шаблоне, не генерируется.

**Отвергнуто:**
- **Свой OpenAPIGenerator из YAML** — дублирует работу FastAPI, два разных OpenAPI = рассинхрон.
- **pydantic2ts** — плохо поддерживается, нужен форк для Pydantic v2, внешняя зависимость вне контроля.
- **Write-once TS стабы (Jinja2)** — нужен свой маппинг типов, TS и Python дрифтят независимо.

### 5. UI Kit: shadcn/ui

Строгий набор компонентов. Минимизация кастомного CSS — предпочтение дизайн-токенам. Экономит контекст и токены при генерации UI.

---

## Принятые решения: Backend кодогенерация

### 6. Переименование SchemasGenerator → ModelsGenerator

Текущий `SchemasGenerator` генерирует ORM/domain-модели из `models.yaml`, но называется "schemas" — путаница с настоящими API-схемами (Create/Read/Update). Переименовать в `ModelsGenerator` для ясности.

### 7. Write-once стабы для роутеров и схем

По аналогии с `ControllersGenerator` (генерирует файл только если его нет, потом не трогает), добавить два новых генератора:

**RouterStubGenerator** — `routers/{module}.py`:
- Базовый CRUD (create/get/list/update/delete) с `APIRouter`, `Depends`, `response_model`
- Access control dependency из спеки (см. п.8)
- TODO-маркеры для бизнес-логики (валидации, кастомные фильтры, каскадные удаления)

**SchemaStubGenerator** — `schemas/{module}.py`, 3 класса на сущность:
- `Create` — поля из models.yaml минус auto-поля (`id`, `created_at`, `updated_at`)
- `Read(Create)` — наследует Create + auto-поля обратно, `model_config = ConfigDict(from_attributes=True)`
- `Update` — отдельный класс (не наследует), все поля Optional. Обновляемые поля — осознанный выбор, не механическая проекция.

Без отдельного `Base`-класса — `Create` и есть база.
**Связи (Foreign Keys)** реализованы через Вариант А (Flat-структура: только ID). Никакой вложенности на этапе чтения MVP (например, возвращается `author_id`, а не объект `User`). Это идеально ложится на Refine и упрощает кодогенерацию. Разработчик может руками написать класс с вложенностью при необходимости.

**Почему write-once, а не перегенерация:** старый `RoutersGenerator` перезаписывал файлы при каждом `make generate`. Это ломало ручные правки и было главной причиной его удаления. Write-once стабы не имеют этой проблемы — генерируют каркас один раз, дальше файл полностью в руках разработчика.

### 8. Access control через спеку

Три уровня задаются декларативно в спеке операции:

```yaml
operations:
  create_project:
    access: admin
  get_project:
    access: user
  list_public_pages:
    access: public
  manage_team:
    access: custom   # escape hatch
```

Генератор подставляет соответствующий `Depends(...)`:
- `public` — без dependency
- `user` — `Depends(require_authenticated_user)`
- `admin` — `Depends(require_admin)`
- `custom` — без dependency + TODO-маркер

Три dependency-функции пишутся один раз в шаблоне проекта.

**Проблема расхождения бизнес-логики:** когда access control становится data-dependent (ownership, team membership), спека не может это выразить. Решение: спека задаёт **минимальный** уровень (floor), контроллер ужесточает при необходимости. `custom` — явный escape hatch для нетипичных случаев.

**Отложено:** уровень `owner` (проверка FK на текущего юзера). Добавить, если паттерн станет повторяющимся в реальных проектах. Преждевременная оптимизация сейчас не оправдана.

### 9. Существующая архитектура Protocol → Controller — без изменений

Текущая архитектура (Protocol как интерфейс контроллера, Controller как бизнес-логика, Router/EventAdapter как транспорт) остаётся. Dual-transport (REST + Events через один контроллер) на практике редко используется, но Protocol полезен как автоматически обновляемый контракт: при изменении спеки IDE сразу подсвечивает рассинхрон с контроллером.

**Открытый вопрос на будущее:** упрощение до "логика в роутере" без промежуточного контроллера — пересмотреть после опыта использования шаблона в реальных проектах.

---

## Полная карта генерации

```
models.yaml (сущности и их поля)
    ├──→ ORM-модели          (ModelsGenerator, перегенерируется)      [переименован]
    └──→ Pydantic-схемы      (SchemaStubGenerator, write-once)        [новое]

operations.yaml (что можно делать с сущностями)
    ├──→ Протоколы           (ProtocolsGenerator, перегенерируется)
    ├──→ Контроллеры         (ControllersGenerator, write-once)
    ├──→ Роутеры             (RouterStubGenerator, write-once)        [новое]
    └──→ Refine dataProvider (перегенерируется)                       [новое]

events.yaml (события между сервисами, слабо связана с models.yaml)
    ├──→ Event-контракты     (EventsGenerator, перегенерируется)
    └──→ Event-адаптеры      (EventAdapterGenerator, перегенерируется)

FastAPI runtime (поднятый бэкенд, отражает кастомизированные схемы и роутеры)
    ├──→ openapi.json        (app.openapi(), коммитится в репо)
    ├──→ TypeScript-типы     (openapi-typescript, перегенерируется)   [новое]
    └──→ Swagger UI docs     (/docs, бесплатно)                      [новое]
```

---

## Порядок реализации

```
Phase 1: Backend стабы
         - Переименование SchemasGenerator → ModelsGenerator
         - SchemaStubGenerator (Create/Read/Update, 3 класса)
         - RouterStubGenerator + access control в спеке

Phase 2: Frontend типы + auth
         - Извлечение OpenAPI из поднятого FastAPI → openapi.json
         - openapi-typescript → TS-типы из openapi.json
         - Параметризация auth через Copier (frontend_auth флаг)
         - Базовый apiClient в scaffold-шаблоне

Phase 3: UI Kit + auth каркас
         - shadcn/ui компоненты
         - AuthContext, ProtectedRoute, страница логина (3 роли)

Phase 4: Refine интеграция
         - dataProvider из operations.yaml
         - authProvider → наш auth-слой
         - Catch-all роут для админки
```

---

### 10. Frontend testing — отложено

Тестирование фронта не включается в шаблон на текущем этапе. Причины:
- Astro islands — мало JS-логики, большинство страниц статические
- Refine-админка — тестировать чужой фреймворк бессмысленно
- Реальной логики для unit/component тестов на старте немного

Пересмотреть после добавления Playwright MCP-агента — тогда E2E smoke-тесты (логин, CRUD, навигация) станут практичными.

---

### 11. Error handling на фронте

Три слоя обработки ошибок в scaffold-шаблоне:

**apiClient (HTTP-ответы):**
- `401 Unauthorized` → очистить токен, редирект на `/login` (в MVP сразу делаем полный flow: interceptor сам пытается дёрнуть `/refresh`, если тот возвращает `401/403` — тогда сброс сессии).
- `403 Forbidden` → throw, обработка на уровне вызывающего кода
- `422 Validation Error` → вернуть структурированную ошибку FastAPI, формы разбирают сами
- `500 / Network Error` → throw, ловится Error Boundary или toast

**Error Boundary:**
- Глобальный `<ErrorFallback>` компонент в scaffold
- Per-island изоляция бесплатно от Astro — один island упал, остальные работают

**UI-нотификации:**
- Toast из shadcn/ui для mutation-ошибок (failed save/delete/update)
- Inline errors под полями форм для validation errors (422)
- Full-page error для 404, 403

---

### 12. Client state management — Context API

React Query (через Refine и напрямую) покрывает серверный стейт. Для клиентского стейта (модалки, формы, тема, sidebar) — **Context API + useState**, без внешних зависимостей.

Обоснование: Astro islands изолированы друг от друга, шаренный стейт между ними минимален. Внутри одного island (Refine-админка) Context API покрывает. Zustand/Jotai оправданы для SPA-масштаба, но с Astro islands этого сценария нет.

В scaffold-шаблоне: `AuthContext` (п.3) + `ThemeContext` (light/dark). Остальное — `useState` в компонентах.

---

### 13. Синхронизация OpenAPI и CI/CD проверки

Экспорт `openapi.json` делается через статический дамп (например, скриптом `scripts/dump_openapi.py`), который инициализирует `app` из FastAPI **без полного запуска стэка**.
Это даёт нам две мощнейшие вещи бесплатно:
1. **Проверка архитектуры:** Статический дамп упадёт, если кто-то из разработчиков написал сетевой код/вызов БД прямо на уровне импортов (модульные сайд-эффекты), что заставит держать код "чистым".
2. **Быстрый CI и pre-push:** Хук `pre-push` сможет за долю секунды проверить, сгенерирован ли актуальный `openapi.json` и совпадают ли типы TypeScript. Это защитит от заливки кода, ломающего типы между фронтом и бэком, а в CI не придётся поднимать БД для проверок.

---

### 14. Кастомные (non-CRUD) операции в Refine

`dataProvider` Refine генерируется и покрывает **только стандартный CRUD**.
Для кастомных бизнес-действий (например: `approve_document`, `ban_user`) мы используем напрямую наш типизированный `apiClient` с вызовом сгенерированных endpoints, в обход `dataProvider`.
Разделение ролей чёткое: Refine = CRUD-таблицы и формы, `apiClient` = все кастомные действия.
