# MIYORI NEXUS — архитектурный аудит и план внедрения

Базовая точка аудита: Miyori `00.00.41`, commit `3409c9f5d0b91c7c9df79aa2d362b49b959a11ae`.
Нормативная основа: `MIYORI_KITSUNE_AI_SPEC_v1.0.0.json` и фактическое поведение текущего проекта.

## Принцип NEXUS

NEXUS — не новый декоративный интерфейс поверх старого приложения. Это совместимый слой состояния,
контрактов и пользовательских поверхностей, который постепенно объединяет Chat, Agents, Memory,
Documents, Home, Voice и будущий Desktop-клиент.

Любое визуальное состояние обязано иметь реальный источник данных. Анимация не может изображать
работу отсутствующего модуля. Генеративный интерфейс не получает права исполнять произвольный HTML
или обходить permission/tool контур.

## Аудит текущей архитектуры

| Область спецификации | Текущее состояние | Оценка | Следующий архитектурный шаг |
| --- | --- | --- | --- |
| Собственный интерфейс | Локальный browser UI + launcher | Частично | Сохранить web UI как базовый клиент; Desktop shell подключить позже к тем же API |
| Cloud.ru | Provider, catalog, connection test, secret masking | Реализовано | Вывести фактический health в NEXUS state, не путать configuration с connectivity |
| Brain / planning | Context Router + model Planner + fallback | Реализовано/частично | Перевести наблюдаемое состояние на единый NEXUS event/state contract |
| Hands / tools | Tool Registry v2, permission, preflight, verify, recovery | Реализовано | Представлять actions через typed UI descriptors, не через произвольную разметку модели |
| Memory | Personal/project scopes, sources, statuses, history | Реализовано | Унифицировать наблюдаемое состояние и future memory surfaces |
| Documents | Drive, originals, trash, RAG, Document Intelligence, exhaustive Q&A | Сильная реализация | Подключить к NEXUS surfaces; OCR/vision остаются отдельным этапом |
| Immune / truth | Epistemic Core, evidence, contradictions, prompt-injection boundary | Реализовано | Сделать truth/evidence first-class NEXUS surface |
| Background work | Persistent tasks, cancel, recovery | Реализовано/частично | Добавить budget/resource layer и события в общий state fabric |
| Nervous system | workflow/task/audit events существуют раздельно | Частично | Ввести единый versioned event envelope без переписывания существующих таблиц |
| Attention | Context Router и приоритет активного запроса | Частично | Отделить attention policy от retrieval policy |
| Digital body | Несколько status chips и существующий `/nexus` snapshot | Частично | Нормализовать состояния `disabled/not_connected/ready/processing/degraded/error` |
| Home | CRUD устройств и parental-control foundation | Частично | Capability API, discovery/heartbeat позже; не смешивать с UI shell |
| Voice / ears / tongue | Нет STT/TTS runtime | Не реализовано | Capability boundary + permission-visible microphone state |
| Desktop | `Miyori.bat`, browser auto-open | Не реализовано как shell | Desktop shell только после стабилизации API/events |
| Generative UI | Нет typed renderer | Не реализовано | Только schema-driven surfaces; arbitrary model HTML запрещён |
| TypeScript/build | Classic JS, frontend build отсутствует | Технический долг | Постепенный TS island, без big-bang rewrite |
| Accessibility | Семантика частичная, нет общего focus/Escape/reduced-motion слоя | Частично | Общий a11y runtime + CI contract |

## Совместимость: обязательные инварианты

1. Текущие REST endpoints и legacy-поля `/api/projects/{id}/nexus` сохраняются.
2. Classic JS остаётся рабочим, пока функциональность не перенесена и не покрыта проверками.
3. TypeScript не становится runtime-зависимостью: браузер получает заранее собранные ES modules.
4. Модель не генерирует и не исполняет HTML/JavaScript. Generative UI работает через ограниченные typed descriptors.
5. `write`-действия продолжают проходить существующий permission/preflight/verify/recovery pipeline.
6. Состояние UI берётся из backend/runtime фактов; speculative animation запрещена.
7. Desktop, Voice и Home подключаются как capabilities, а не как специальные обходные пути вокруг Core.

## Поэтапный план

### N0 — NEXUS Foundation

- versioned NEXUS snapshot;
- единые operational states;
- TypeScript island и воспроизводимая сборка;
- accessibility runtime: focus trap, Escape, focus return, reduced motion;
- typed Generative UI boundary;
- frontend CI gate.

### N1 — State & Event Fabric

- versioned event envelope;
- адаптер существующих task/workflow/audit events;
- client state store;
- reconnect/resync без потери состояния;
- никакой новой анимации без event source.

### N2 — NEXUS Shell

- единая навигация Chat / Actions / Knowledge / Home / System;
- progressive disclosure вместо постоянной панели технических деталей;
- command surface и keyboard navigation;
- responsive layout для будущего Desktop shell.

### N3 — Agents & Actions

- action center: running / waiting permission / recovery / complete;
- typed previews и confirmations;
- progress/evidence/result surfaces;
- без дублирования workflow state в frontend.

### N4 — Knowledge

- Memory + Documents + Epistemic как связанные, но не смешанные источники;
- source/evidence navigation;
- document coverage и exhaustive verification surfaces;
- безопасные контекстные действия.

### N5 — Voice

- explicit microphone capability;
- STT transcript with timestamps/confidence;
- TTS queue/state;
- visible recording/listening states;
- interrupt/cancel semantics.

### N6 — Desktop

- shell поверх существующего API;
- tray, autostart, deep links, native notifications;
- launcher/update/recovery остаются независимыми от AI provider.

### N7 — Home

- discovery/heartbeat/device identity;
- online/offline evidence;
- parental-control rules only for explicitly linked devices;
- audit trail для действий.

### N8 — Digital Body / Avatar

Только после реальных state/event источников. Взгляд, речь, ожидание, ошибка и работа отображают
конкретные состояния runtime; случайная «живость» не используется как имитация интеллекта.

## Gate после каждого этапа

- Python unit/integration tests;
- TypeScript `strict` typecheck;
- воспроизводимая frontend build и проверка committed artifacts;
- UI state contract tests;
- accessibility static contract + keyboard/focus runtime;
- отсутствие регрессий legacy API/JS;
- отдельная проверка, что новые визуальные состояния имеют фактический data source.
