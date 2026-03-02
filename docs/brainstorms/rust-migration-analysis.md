# Rust Migration Analysis

**Status**: RESEARCH / LONG-TERM VISION
**Horizon**: ~1 year
**Date**: 2026-03-01

## Мотивация

Этот шаблон создан в первую очередь для AI-агентов (см. `MANIFESTO.md`). Rust даёт принципиальное преимущество для agent-driven разработки: **строгий и быстрый цикл обратной связи через компилятор**.

- На Python агент может зашипить код, который упадёт в продакшне на edge case
- На Rust — если код скомпилировался, он с высокой вероятностью корректен ("if it compiles, it's ~correct")
- Компилятор Rust выдаёт детальные, самодокументирующиеся ошибки — идеальный feedback loop для LLM

## Данные: AI + Rust (начало 2026)

### Бенчмарки

| Бенчмарк | Python | Rust | Комментарий |
|---|---|---|---|
| SWE-bench Multilingual | 63% | 58.14% | Rust — лучший среди не-Python языков |
| Multi-SWE-bench (repository-level) | 52.2% | 15.9% | Большой gap на уровне реальных репозиториев |
| DevQualityEval (function-level) | ~99% | ~99% | Gap закрыт на уровне функций |
| Aider Polyglot | Strong | Strong | Почти паритет на алгоритмических задачах |

### Ключевые исследования

- **RustAssistant** (Microsoft Research, ICSE 2025): 74% успеха в автоисправлении compile errors через LLM ↔ compiler loop. `cargo fix` справляется с <10%
- **RustEvo2**: на API после knowledge cutoff моделей успех падает с 56% до 32.5% — быстрая эволюция Rust API создаёт "движущуюся мишень"
- Консенсус: *"Typed languages make AI coding significantly easier. Rust, with its memory model captured by the type system, is perhaps the best case for this"*

### Тренд

Gap закрывается. Для function-level задач он уже закрыт. Для repository-level — сокращается, но ещё значителен. Через год ожидается существенное улучшение.

### Данные обучения

Python имеет ~10-20x больше кода на GitHub. Но Rust-код качественнее: единообразный стиль (rustfmt), единая структура проектов (cargo), культура тестов и CI.

## Экосистема Rust: соответствия текущему стеку

| Текущий компонент | Rust-эквивалент | Зрелость |
|---|---|---|
| FastAPI | **Axum** (23.6k stars, Tokio team) | Зрелый |
| SQLAlchemy + Alembic | **SeaORM 2.0** (автомиграции из entities, Jan 2026) | Свежий но рабочий |
| Pydantic | **serde** + validation crates | Зрелый |
| FastStream (Redis pub/sub) | Нет прямого аналога (redis-rs + custom) | Пробел |
| Taskiq / Celery | **Apalis** (1k stars, RC) | Незрелый |
| python-telegram-bot | **teloxide** (3.4k stars) | Зрелый |
| httpx | **reqwest** | Зрелый |
| OpenAPI generation | **utoipa** (15M downloads) | Зрелый |
| copier | copier (language-agnostic) | N/A |
| per-service venvs | **Cargo workspaces** | Лучше чем в Python |
| lazy broker | **OnceLock / LazyLock** | Stdlib |

### Критические пробелы

1. **Task queue** — Apalis единственный живой вариант, и он в RC. Нет мониторинг-UI (Flower-аналог). Нет multi-broker абстракции
2. **FastStream-аналог** — нет готового фреймворка для event-driven Redis pub/sub с декларативными подписками
3. **datamodel-code-generator** — нет аналога для JSON Schema → Rust structs (придётся писать свой codegen)

### Что станет проще в Rust

- `typing.Protocol` → нативные Rust traits (проще и строже)
- Per-service venvs → Cargo workspaces (один lockfile, одна команда)
- Lazy initialization → `std::sync::OnceLock`
- Spec compliance → compile-time guarantees

## Стратегия постепенной миграции

### Фаза 0: Подготовка (сейчас)

Не менять ничего в Python-шаблоне, но ориентировать архитектурные решения на language-agnostic:

- YAML-спеки должны использовать JSON Schema типы, не Python-специфичные
- Transport abstraction (REST/events в одном spec) — уже переносима
- Protocol-based DI → в Rust это traits
- Новый код и спеки писать максимально агностично к языку

### Фаза 1: Proof of Concept (через 2-3 месяца)

- Взять один сервис (`backend`) и написать Rust-аналог на Axum + SeaORM 2.0 + utoipa
- Тот же API, тот же Docker, тот же compose — другая реализация внутри контейнера
- Проверить: насколько AI-агент справляется с генерацией Axum-кода

### Фаза 2: Codegen pipeline на Rust (3-6 месяцев)

- Переписать `framework/` на Rust: spec parser + code generators
- Использовать **Tera** (Jinja2-подобный) для шаблонов
- Codegen на Rust сам будет строго типизирован — ошибки в генераторе ловятся при компиляции

### Фаза 3: Полный шаблон (6-12 месяцев)

- К этому моменту Apalis скорее всего выйдет из RC
- SeaORM 2.0 обрастёт документацией и стабилизируется
- AI-модели будут ещё лучше в Rust

## Риски

| Риск | Серьёзность | Митигация |
|---|---|---|
| Multi-SWE-bench gap (16% vs 52%) | Высокая | Через год будет меньше; compile loop помогает |
| Task queue ecosystem незрел | Средняя | Loco имеет встроенный; Apalis выйдет из RC |
| Сотни часов на переписывание | Высокая | Постепенная миграция, сервис за сервисом |
| Агенты хуже знают Rust | Средняя | Тренд на улучшение; хорошие AGENTS.md компенсируют |
| Нет FastStream-аналога | Средняя | Простой Redis pub/sub на redis-rs — несложно |

## Конкретные задачи

Задачи, которые можно делать уже сейчас, описаны в `docs/backlog.md` в секции **Rust Migration Preparation**.
