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
| Digital body | Persona canon + Presence/Voice runtime + Appearance Profile + trusted renderer registry | Реализовано/частично | Добавить реальный dynamic renderer как новый trusted adapter после появления совместимого asset; arbitrary asset JS запрещён |
| Home | Inventory + authenticated heartbeat + explicit parental binding | Реализовано/частично | Подключить реальные device-agents/OS adapters позже; не симулировать enforcement |
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

## Фактический прогресс

- **N0 / 00.00.42 — завершён.** Versioned snapshot, operational states, TypeScript island, typed UI boundary, accessibility runtime и frontend CI опубликованы без замены legacy UI.
- **N1 / 00.00.43 — завершён.** Existing audit/workflow/task journals объединены read-only event adapter-ом; добавлены cursor/tail, project isolation и TypeScript NexusStore с authoritative snapshot resync.
- **N2 / 00.00.44 — завершён.** Введён совместимый NEXUS Shell с пятью primary-разделами, state-driven badges, Actions workspace, keyboard/mobile navigation и progressive disclosure legacy-функций.
- **00.00.45 — инфраструктурный hotfix.** Portable Launch Reliability исправляет ZIP/Windows entrypoint и добавляет Windows archive CI; NEXUS-функциональная архитектура N0–N2 не меняется.
- **N3 / 00.00.46 — завершён.** Agents & Actions: единый versioned Action Contract, deduplication permission↔workflow, реальные planned/waiting/running/verifying/recovery/completed/error states, preview/evidence/result/history surfaces и точные state-driven badges.
- **N4 / 00.00.47 — завершён.** Knowledge: отдельный versioned Knowledge Contract объединяет навигацию по Memory + Documents + Epistemic без смешивания сущностей; добавлены provenance/evidence, extraction/analysis/exhaustive coverage, grouped search, safe actions и спокойный progressive-disclosure UI.
- **N5 / 00.00.51 — завершён.** Voice Core: versioned state/safety protocol, explicit microphone permission, optional browser STT, transcript/confidence, opt-in TTS, interruption/barge-in и Living Presence integration.
- **N6 — запланирован.** Desktop Runtime: native shell поверх существующего API.
- **N7 / 00.00.48 — завершён.** Generative UI: trusted component registry, versioned surface specs, safe renderer без model-authored HTML/JS и quiet surface shelf.
- **N8 / 00.00.52 — завершён.** Agent Workspace: persistent DAG coordinator поверх Workflow Engine, parallel-ready execution, per-node/total budgets, dependency handoff, approvals/recovery inheritance и отдельная Actions surface.
- **N9 / 00.00.49 — завершён.** Living Presence: versioned presence contract выводит ready/working/waiting/attention/recovery/degraded только из NEXUS snapshot, Actions, Events и реального локального chat-request state; idle остаётся визуально тихим.
- **N10 / 00.00.50 — завершён.** Proactive Miyori: canonical attention engine, state fingerprinting, persistent snooze/dismiss, initiative-aware chat shelf, channel ownership и запрет автоматического write/chat interruption.
- **N11 / 00.00.53 — завершён.** Home: explicit device identity, one-time heartbeat credential, TTL connectivity evidence, capability allowlist, parental binding и отдельная evidence-first Home surface. Legacy status не является connectivity; network scanning и fake OS enforcement запрещены.
- **N12 / 00.00.54 — Digital Body Runtime завершён.** Persona canon связан с Presence/Voice/interaction state; fake liveness и sentiment inference запрещены. Финальный portrait asset намеренно остаётся не настроенным до выбора владельцем цвета волос, цвета глаз, точного числа хвостов и основного наряда.
- **N12.1 / 00.00.55 — завершён.** Owner-global Appearance Profile хранит четыре открытых выбора без системных дефолтов; static portrait adapter отделён от account avatar и честно объявляет отсутствие dynamic pose/expression.
- **N12.2 / 00.00.56 — завершён.** Trusted Body Renderer Registry отделяет state от renderer; neutral/static adapters установлены, unknown adapters fail closed.
- **N12.3 / 00.00.57 — завершён.** Real Dynamic Renderer Integration устанавливает built-in `trusted_vector_rig`: deterministic DOM/CSS motion потребляет только pose/expression/gesture/state, respects reduced motion и не придумывает owner appearance choices.
- **N12.4 / 00.00.58 — завершён.** Miyori Character Rig добавляет полнофигурный `trusted_character_rig`: лицо, волосы, уши, тело, руки, ноги, neutral outfit layer и owner-driven tails. Незаданные owner choices остаются нейтральными и не выводятся из модели.
- **00.00.59 — Unified Interface завершён.** Shell, Chat, Actions, Knowledge, Home и Settings приведены к одной visual system; ultra-wide растяжение ограничено, legacy project/conversation rail скрыт, дублирующие технические заголовки удалены.
- **00.00.61 — Chat Productivity.** Проектные ID вложений валидируются сервером, выбранные фрагменты документов передаются отдельно от RAG; сообщения и события не перезаписываются при редактировании, создаётся fork. История постранична, источники и закладки сохраняются, верхние аватар и значок рядом с Миёри удалены полностью. Версионированный Digital Body остаётся доступен только в owner Appearance editor.
- **00.00.60 — Conversation Redesign.** ChatGPT-подобные принципы ввода без копирования продукта: многострочный composer, доступная история, безопасный Markdown (локальные Marked + DOMPurify), Digital Body как компактное состояние в заголовке; Appearance Profile и Settings доступны из Дополнительно. Действия получили пользовательские формулировки, source-of-truth, permissions и runtime состояния не менялись. Portable launcher одновременно исправлен для Uvicorn `_Tee.isatty` compatibility.
- **N6 Desktop Runtime остаётся отложен по решению владельца проекта. Следующий шаг после N12.3 — либо подключение финального character asset к trusted dynamic adapter, либо переход к N6 Desktop Runtime; operational state contract менять не требуется.**

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

### N7 — Generative UI

- versioned surface contract;
- закрытый component registry;
- только trusted renderer components;
- model-authored HTML/JavaScript запрещены;
- contextual surfaces не засоряют Chat и раскрываются по запросу.

### N8 — Agent Workspace

- delegation и parallel work;
- dependency graph;
- budgets, approvals и handoff;
- отдельный agent workspace без превращения Chat в control room.

### N9 — Living Presence

- presence выводится из реальных snapshot/event/action/task states;
- waiting / working / attention / degraded имеют конкретные data sources;
- никакой случайной анимации или симуляции «жизни».

### N10 — Proactive Miyori

- server-side attention budget;
- deduplication и persistent dismiss/snooze;
- proactive suggestions не выполняют write-actions автоматически;
- Chat остаётся тихим: low-priority сигналы живут вне потока сообщений.

### N11 — Home

- discovery/heartbeat/device identity;
- online/offline evidence;
- parental-control rules only for explicitly linked devices;
- audit trail для действий.

### N12 — Digital Body / Avatar

- versioned body-state contract поверх Living Presence;
- explicit local Voice/interaction override без второго источника истины;
- Persona Pack разделяет confirmed appearance и owner-open choices;
- нейтральная оболочка не фиксирует цвет волос, глаз, число хвостов или наряд;
- pose/expression/gesture отображают конкретные runtime states;
- random liveness, timer idle animation, sentiment→emotion и model-authored motion запрещены;
- owner-global Appearance Profile хранит открытые выборы отдельно от Persona Pack и project state;
- static portrait adapter не заявляет dynamic pose/expression;
- renderer выбирается через закрытый trusted registry; arbitrary asset-authored JavaScript запрещён;
- unknown adapter fail-closed использует neutral shell;
- built-in `trusted_vector_rig` установлен как первый dynamic adapter и не меняет operational state contract;
- `trusted_character_rig` является полнофигурным owner-aware adapter поверх тех же presentation channels;
- финальный character asset может быть подключён позже отдельным trusted adapter без model-authored code и без изменения source-of-truth.

## Gate после каждого этапа

- Python unit/integration tests;
- TypeScript `strict` typecheck;
- воспроизводимая frontend build и проверка committed artifacts;
- UI state contract tests;
- accessibility static contract + keyboard/focus runtime;
- отсутствие регрессий legacy API/JS;
- отдельная проверка, что новые визуальные состояния имеют фактический data source.

- **00.00.62 — безопасные Fork / Retry.** Edit/regenerate сохраняет исходную историю без побочных эффектов: серверный `read_only` принудительно исключает инструменты, при сбое повторяет прежний idempotency key только внутри того же проекта, диалога и списка вложений. Исполненные workflow нельзя молча повторять.

- **00.00.63 · Chat Intelligence.** Продолжения разговора разрешают только расширение retrieval-контекста (документы и verified memory) в пределах текущего project/conversation; не наследуют tool permissions и не меняют read-only forks. Реальные usage/latency Cloud.ru и evidence-availability записываются вместе с ответом. Отсутствующий API usage остаётся неизвестным; наличие источников не является семантической проверкой результата.

- **00.00.64 — Document Reasoning.** Многодокументная проверка через уже существующий persistent Exhaustive Q&A, evidence с locator, реальный OCR/extraction coverage и запуск по явному действию пользователя в компактной карточке.

- **00.00.65 — Agent Continuation.** Compact persisted task status shown only on actual pending work; links into NEXUS Actions for permission/recovery. No automatic tool execution, no synthetic progress, no new memory architecture.

- **00.00.66 — Chat Reliability.** Отображение состояния проектов и аналитика не образуют второй агентный контур. Обновление только затронутых модулей выполняется после подтверждённого ответа, фоновый отказ статистики не означает ошибки самого чата. Usage Cloud.ru агрегируется лишь по запросу пользователя, без выдуманных цен.

- **00.00.67 — Project-scoped Chat Recall / System Menu.** Старые сообщения — исключительно непроверенные цитаты из текущего проекта. Они извлекаются лишь по явной просьбе, имеют conversation/message provenance и никогда не используются как tool authority. «Состояние системы» перенесено в верхнюю точку меню; исходные runtime ID статуса не дублируются, значения отображаются в едином окне. «Дополнительно» — постоянная область навигации без disclosure.

- **00.00.68 — Numerical Answer Check.** Проверка конкретных чисел/дат в извлечённых источниках встроена в диагностику ответа; не запускает LLM ещё раз, не превращает совпадение слов в верификацию фактов и не повышает confidence Epistemic Core. Непроверенные прежние разговоры исключены из доказательств.

- **00.00.69 — Correction Feedback.** Явные пользовательские правки записываются append-only в project-scoped chat_feedback_events (original assistant message provenance), используются только в релевантном текстовом контексте и никогда не повышают verified knowledge или инструментальные разрешения. UI-inline формы открываются только нажатием «Исправить», без новых панелей. Feedback statistics — измеримые события, не показатель объективной точности.

- **00.00.70 — Chat Startup/Networking.** Независимые стартовые данные загружаются параллельно. Critical-path — history + authoritative NEXUS; технические разделы не блокируют композер. Client API объединяет только одновременные одинаковые GET без опций и никогда не сохраняет результат после завершения запроса, не разделяет abortable/mutating запросы. Фактическую латентность конкретной установки следует измерить отдельно.

- **00.00.71 — Exact Document Candidate Linking.** В уже существующем Document Intelligence разделе доступен ленивый локальный read-only поиск совпавших VIN, госномеров, номеров договоров/счетов с указанием `document_nodes.locator` двух файлов. Запрос строго project-scoped, исключает корзину, не выдаёт кандидата за факт и отмечает усечённую выборку. Только по явному раскрытию пользователем.

- **00.00.72 — Screen Context Hints.** Клиент передаёт module + last-viewed document ID, сервер нормализует enum и project-scoped ownership. Документная выдача активируется только явной ссылкой пользователя на «этот» документ. Результат — минимальные source-cited snippets, не permission и не новая agent-команда. Request-ID повтор требует тождественный экранный контекст; новая беседа/проект очищает ID.
