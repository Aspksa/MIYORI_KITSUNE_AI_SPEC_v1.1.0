# Miyori Kitsune AI

Локальный персональный AI-проект с FastAPI backend, SQLite-хранилищем, Cloud.ru LLM, Persona Pack, RAG, Epistemic Core, проектными пространствами и модульным веб-интерфейсом.

**Внутренняя версия приложения: 00.00.41.**  
Репозиторий: `Aspksa/MIYORI_KITSUNE_AI_SPEC_v1.1.0`.

## Состояние релиза 00.00.41

`00.00.41` — **Extraction Integrity · честная полнота чтения оригинала**.

После `00.00.40` Miyori умеет доказуемо пройти весь **извлечённый** текст по конкретному вопросу. `00.00.41` отделяет это от другой задачи: насколько полно сам parser смог прочитать исходный файл.

Теперь у документа две независимые метрики:

- **extraction coverage** — какая доля исходного файла доступна текстовому parser-у;
- **AI coverage** — какая доля уже извлечённого текста реально прошла глубокий анализ.

Это важно для сложных PDF/Office-файлов: AI coverage может быть 100%, но extraction coverage — меньше 100%, если часть страниц является сканом, слайд состоит только из изображения или в документе есть визуальные объекты, которые пока не интерпретируются.

Что добавлено:

- PDF считает страницы с текстовым слоем и отдельно перечисляет страницы без извлекаемого текста;
- DOCX извлекает основной текст, таблицы, headers/footers, footnotes/endnotes/comments; media/charts фиксируются как непроанализированная визуальная часть;
- XLSX сохраняет формулы даже без cached value и отмечает изображения/диаграммы;
- PPTX учитывает слайды без текста, speaker notes, media и charts;
- Document Intelligence хранит persistent extraction manifest: status, coverage, warnings, details;
- exhaustive Q&A хранит scan coverage, source extraction coverage и overall coverage;
- при неполном извлечении exhaustive-ответ получает обязательный caveat, а confidence не остаётся `high`;
- Drive показывает две отдельные шкалы и предупреждения по оригиналу;
- миграция старой SQLite выполняется in-place и не стирает историю анализа/вопросов.

Важно: OCR и полноценный multimodal vision ещё не реализованы. `00.00.41` не скрывает этот пробел, а делает его измеримым и видимым.

## Состояние релиза 00.00.40

`00.00.40` — **Exhaustive Document Q&A**.

Miyori теперь различает быстрый retrieval и доказуемую проверку всего документа. Обычный RAG выбирает наиболее релевантные фрагменты; exhaustive-режим последовательно проверяет **каждое окно извлечённого текста** по конкретному вопросу и только после этого строит итоговый ответ.

- отдельные persistent `document_questions` и `document_question_windows`;
- собственный `coverage_ratio` для каждого вопроса;
- evidence обязательно сохраняет locator к месту документа;
- нерелевантное окно тоже считается проверенным, а не пропущенным;
- после сбоя уже проверенные окна переиспользуются по SHA-256 fingerprint содержимого;
- одинаковый вопрос к неизменному оригиналу переиспользует готовый/активный run;
- в Drive блок «Спросить по всему документу» показывает прогресс, ответ и доказательства;
- сканированные PDF без текстового слоя по-прежнему честно требуют OCR.

## Состояние релиза 00.00.39

`00.00.39` — **Document Intelligence · полное понимание документов и книг**.

Основной принцип релиза: длинный документ больше не считается просто набором найденных фрагментов. Miyori строит постоянную структурную модель документа и может последовательно пройти весь извлечённый текст от начала до конца.

- при загрузке оригинала сразу строится локальная карта документа: структура, порядок, locator-ы, outline и метрики;
- TXT/Markdown распознают заголовки и уровни; DOCX — заголовки, параграфы и таблицы; PDF — страницы и структурные блоки; XLSX — листы и диапазоны строк; PPTX — слайды; JSON — JSON-path;
- глубокий AI-анализ выполняется по окнам всего документа, а затем результаты объединяются многоуровневым map→reduce synthesis;
- `coverage_ratio` показывает фактическую долю извлечённого текста, прошедшую глубокий AI-анализ;
- статус `complete` ставится только при практически полном покрытии текста;
- результаты сохраняют locator-ы к местам документа;
- уже обработанные окна переиспользуются после перезапуска, если структура документа не изменилась;
- running background tasks после аварийного завершения возвращаются в очередь;
- Agent Core получил инструменты целостного понимания, outline и глубокого структурного поиска;
- Document Intelligence участвует в RAG как отдельный retrieval-канал;
- в Miyori Drive появился экран «Понимание документа» со сводкой, структурой, coverage, ключевыми пунктами, рисками и сущностями.

Важно: «полное понимание» относится ко всему **извлечённому тексту** документа. Сканированный PDF без текстового слоя сохраняется как оригинал, но получает статус `needs_ocr` и не помечается как полностью понятый до появления OCR-контура.

## Что уже реализовано

### Miyori AI

- чат с Cloud.ru Foundation Models;
- Persona Pack `2.0.0`;
- локальный контекст проекта;
- Brain plan;
- Context Router для выборочной загрузки контекста;
- Agent Core v2.2 с model-assisted Planner и deterministic fallback;
- persistent Workflow Engine для многошаговых задач;
- Document Intelligence для целостного понимания длинных документов и книг;
- до 5 проверяемых инструментальных шагов на один workflow;
- продолжение того же workflow после permission;
- компактный conversational context для ссылок «этот файл / перемести его»;
- Tool Registry v2 с schema/risk/recovery metadata;
- инструменты чтения и контролируемые действия;
- разрешения на write-действия;
- idempotency для chat и write-tools;
- Audit Trail и recovery после перезапуска;
- фоновые задачи и self-check;
- системный статус и диагностика.

### Память и знания

- SQLite-память с отдельными слоями `user` и `project`;
- working memory остаётся в текущем разговоре и не превращается автоматически в долговременную;
- статусы фактов и ручная работа с памятью;
- Epistemic Core: claims, sources, evidence, contradictions;
- внутренние статусы `candidate / supported / verified / disputed / rejected / superseded`;
- пользовательские оценки уверенности: «Подтверждено / Вероятно / Есть противоречия / Недостаточно данных»;
- RAG по документам, проверенной памяти и подтверждённым знаниям;
- FTS5 при наличии и lexical fallback;
- RRF-объединение каналов поиска.

### Документы / Miyori Drive

Miyori Drive сохраняет оригинал файла байт-в-байт и отдельно строит два слоя знаний.

**RAG-слой** сохраняет совместимые текстовые чанки для быстрого поиска и обычных ответов.

**Document Intelligence** хранит постоянную структурную карту документа:

- заголовки и уровни;
- страницы / слайды / листы / таблицы / JSON-path;
- последовательные структурные узлы;
- точные locator-ы;
- количество слов, страниц, разделов и таблиц;
- outline;
- локальную сводку;
- результаты глубокого анализа и фактическое покрытие текста.

Для больших документов глубокий анализ не пытается поместить всю книгу в одно context window. Текст последовательно разбивается на контролируемые окна, каждое окно анализируется отдельно, после чего результаты сводятся иерархически. Это позволяет обрабатывать документы значительно больше контекстного окна модели без молчаливого пропуска середины книги.

После сбоя уже сохранённые окна анализа переиспользуются. Если оригинал/структура изменилась, границы или locator-ы не совпадут и соответствующее окно будет обработано заново.

Поддерживаемые для извлечения форматы: TXT, Markdown, JSON, PDF с текстовым слоем, DOCX, XLSX и PPTX. Неподдерживаемый файл всё равно может храниться как оригинал. Сканированный PDF без текстового слоя требует OCR.

Каждый проект имеет отдельное физическое хранилище:

```text
data/
  workspace/
    <project_id>/
      Документы - Облако - Miyori/
        Файлы/
        Корзина/
```

Удаление остаётся мягким: оригиналы перемещаются в локальную корзину, исключаются из активного RAG и могут быть восстановлены.

### Проекты

Есть рабочие и домашние проектные пространства, включая модули АО «Примавтодор», сотрудников, контрагентов, договоров, счетов / предложений, домашних устройств и профилей детского контроля.

### Домашнее пространство

**Домашняя сеть** сейчас реализована как CRUD-реестр устройств: имя, тип, адрес, статус и заметка.

Активное сетевое обнаружение, ping/heartbeat, MAC discovery и автоматический мониторинг устройств пока не реализованы.

**Детский контроль Miyori** находится на стадии foundation. Есть профили, устройство, дневной лимит, bedtime и категории блокировок.

Фактическое применение ограничений на телефоне требует отдельного мобильного клиента и явной привязки устройства. Скрытый мониторинг не является частью текущей реализации.

### Аккаунт и настройки

- локальный профиль и аватар;
- device sessions;
- Cloud.ru API key с маскированием секрета;
- выбор модели и проверка подключения;
- тема, плотность и стартовый экран;
- automation/updater;
- Windows autostart;
- системная диагностика и очистка runtime/logs.

### Обновление

Поддерживаются Git fast-forward update и Portable ZIP updater с резервным копированием заменяемых файлов. Пользовательские `.env`, `data`, `logs`, `runtime`, `.venv` и `.git` не должны перезаписываться portable-обновлением.

## Архитектура

### Backend

- `app.py` — FastAPI API и orchestration;
- `miyori/db.py` — основная SQLite-модель;
- `miyori/provider.py` — Cloud.ru provider;
- `miyori/brain.py` — публичный операционный план;
- `miyori/context_router.py` — маршрутизация памяти, документов, знаний и tools;
- `miyori/document_intelligence.py` — document graph, outline, coverage, глубокий поиск и hierarchical map→reduce;
- `miyori/document_questions.py` — exhaustive Q&A по всему документу, evidence, scan/source/overall coverage и fingerprint recovery;
- `miyori/planner.py` — Planner schema, fallback и безопасная валидация решений;
- `miyori/agent.py` — persistent/resumable Agent Workflow Engine;
- `miyori/sources.py` — манифест источников ответа;
- `miyori/tools.py` — Tool Registry v2, validation, preflight, verify, idempotency и recovery;
- `miyori/hands.py` — безопасные workspace-действия;
- `miyori/rag.py` — retrieval;
- `miyori/epistemic.py` — epistemic knowledge layer;
- `miyori/persona.py` — Persona Pack;
- `miyori/tasks.py` / `background.py` — фоновые задачи;
- `miyori/system_settings.py` — настройки и диагностика;
- `miyori/updater.py` / `portable_updater.py` — обновление;
- `miyori/module_registry.py` — версии модулей и changelog.

### Frontend с 00.00.35

JavaScript загружается в фиксированном порядке:

1. `static/js/core.js`
2. `static/js/data.js`
3. `static/js/chat.js`
4. `static/js/workspace.js`
5. `static/js/drive.js`
6. `static/js/projects.js`
7. `static/js/settings.js`
8. `static/js/boot.js`

CSS загружается в фиксированном cascade-порядке:

1. `static/css/foundation.css`
2. `static/css/chat.css`
3. `static/css/workspace.css`
4. `static/css/drive.css`
5. `static/css/modules.css`
6. `static/css/modes.css`
7. `static/css/audit.css`

Порядок файлов является частью frontend-контракта и не должен произвольно меняться.

## Фундамент дальнейшего развития

Workflow Engine специально не привязан к одному типу проекта. На его контракты могут опираться следующие поколения Miyori без смены базовой модели исполнения:

- Document Intelligence: извлечение реквизитов, сравнение договоров, реестры, risk flags и генерация итоговых документов;
- Autonomous Workflows: сохранённые сценарии, события, расписания, фоновые проверки и продолжительные задачи;
- мобильный клиент: тот же workflow/permission/audit contract через отдельный безопасный transport layer;
- бизнес-модули: договоры, счета, сотрудники, гараж, табели и будущие доменные инструменты;
- домашняя автоматизация: устройства и правила с теми же risk/permission/recovery принципами;
- будущий policy layer: разные уровни автономности, бюджеты действий, роли и capability scopes.

Ключевой принцип: новые возможности добавляются как инструменты и workflow policies, а не через обход permission, project isolation или audit trail.

## Локальные данные и безопасность

- SQLite и проектные файлы хранятся локально;
- Cloud.ru API key не возвращается клиенту в открытом виде;
- write-инструменты требуют разрешения;
- устаревшее подтверждение блокируется verify-before-write;
- повторный HTTP/tool request защищён idempotency key;
- незавершённые write-операции после перезапуска переходят в recovery вместо слепого повтора;
- project workspace защищён от path traversal;
- локально-чувствительные account/settings операции ограничены loopback-доступом;
- RAG/Memory/Epistemic блоки передаются модели как данные, а не как инструкции.

## Запуск на Windows

Основной portable-сценарий:

```bat
Miyori.bat
```

Launcher использует bundled runtime при наличии, иначе системный Python / локальную `.venv`; при необходимости portable Python подготавливается через `setup-portable.ps1`. Затем выполняются updater, подготовка `.env`, установка зависимостей и запуск `app.py`.

## Конфигурация

Минимальный `.env`:

```env
CLOUDRU_API_KEY=
CLOUDRU_BASE_URL=https://foundation-models.api.cloud.ru/v1
CLOUDRU_MODEL_ID=deepseek-ai/DeepSeek-V4-Flash
```

Дополнительные параметры запуска и updater приведены в `.env.example`.

## Тесты

GitHub Actions запускает полный `unittest`-контур на push/PR.

Document Intelligence дополнительно проверяет:

- сохранение Markdown-outline и locator-ов;
- структурный поиск с соседним контекстом;
- глубокий анализ длинного документа через несколько окон;
- `coverage_ratio ≈ 100%` после полного прохода;
- повторное использование уже проанализированных окон;
- возвращение interrupted background task в очередь после перезапуска;
- участие Document Intelligence в RAG;
- наличие новых Document Intelligence tools в Tool Registry.

Существующий контур также продолжает проверять Account, Persona, RAG, Epistemic Core, Miyori Drive, Context Router, Planner, memory layers, project isolation, permissions, Tool Registry v2, idempotency, crash recovery, SQLite migrations и интеграционный workflow `/api/chat → permission → resume`.

## Текущие ограничения

- Planner уже model-assisted, но при недоступности Cloud.ru намеренно переключается на ограниченный deterministic fallback;
- workflow имеет консервативный лимит до 5 инструментальных шагов; увеличение бюджета должно сопровождаться budget/policy governance;
- конфликтное recovery-состояние намеренно требует ручной проверки вместо автоматического перезаписывания данных;
- мобильный iOS/Android клиент ещё не реализован;
- детский контроль пока не применяет политики на реальном устройстве;
- домашняя сеть пока не выполняет автоматическое обнаружение;
- OCR для сканированных PDF пока отсутствует: такие файлы сохраняются, но получают `needs_ocr`;
- глубокий AI-анализ требует настроенного Cloud.ru; локальная структура документа строится без него;
- анализ изображений, схем и визуальной верстки внутри документов пока не является полноценным multimodal-контуром;
- автоматический внешний web research не является частью текущего backend-контура.

## Версии

- `00.00.34` — домашние модули + полный UI audit + удаление processing UI;
- `00.00.35` — документация + frontend modularization + удаление processing legacy;
- `00.00.36` — физический Miyori Drive проекта + оригиналы + безопасная корзина + восстановление + поиск по содержимому;
- `00.00.37` — Miyori AI Core v2: Context Router + Planner + Agent loop + layered memory + sources + epistemic assessments + tool safety tests;
- `00.00.38` — AI Reliability & Workflow Engine: persistent workflows + permission resume + idempotency + Tool Registry v2 + audit + crash recovery + CI;
- `00.00.39` — Document Intelligence: structural document graph + hierarchical full-text analysis + coverage tracking + deep search + Drive UI + Agent/RAG integration;
- `00.00.40` — Exhaustive Document Q&A: all-window verification + evidence/locators + question coverage + fingerprint recovery;
- `00.00.41` — Extraction Integrity: source extraction coverage + Office/PDF completeness manifest + truthful exhaustive coverage.

Канонический changelog приложения доступен через `miyori/module_registry.py` и API manifest/changelog.
