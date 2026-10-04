# Miyori Kitsune AI

Локальный персональный AI-проект с FastAPI backend, SQLite-хранилищем, Cloud.ru LLM, Persona Pack, RAG, Epistemic Core, проектными пространствами и модульным веб-интерфейсом.

**Внутренняя версия приложения: 00.00.50.**  
Репозиторий: `Aspksa/MIYORI_KITSUNE_AI_SPEC_v1.1.0`.

## Состояние релиза 00.00.50

`00.00.50` — **NEXUS Proactive Miyori · инициативность с attention budget**.

N10 добавляет инициативность как отдельный безопасный attention layer, а не как поток непрошеных сообщений:

- новый `/api/projects/{id}/nexus/proactive` вычисляет сигналы из реального Actions/Knowledge state;
- сигнал получает стабильный ID из project + source fingerprint;
- persistence хранит только пользовательское решение `dismissed/snoozed`, а не копию workflow/knowledge;
- dismiss и snooze переживают перезапуск;
- snooze ограничен сервером диапазоном 15 минут – 7 дней;
- новая реальная проблема получает новый signal ID и не скрывается старым dismiss;
- attention budget зависит от `initiative_level`: low = 1, medium = 2, high = 3 видимых сигнала;
- low-priority knowledge suggestion допускается только в пределах отдельного low-budget;
- `suggest_next_steps=false` отключает необязательные Knowledge suggestions, но не скрывает ожидающие решения/recovery/errors;
- каждый signal contract жёстко задаёт `auto_execute_allowed=false`, `write_tools_allowed=false`, `chat_interruption_allowed=false`, `creates_chat_message=false`;
- UI — закрытый по умолчанию «Миёри заметила», расположенный вне message stream;
- доступны только явные действия пользователя: открыть нужный раздел, «Позже» или «Скрыть»;
- proactive inbox подавляет дублирующий Generative UI shelf, чтобы одна причина не отображалась дважды;
- refresh использует реальный NEXUS event identity, а не таймеры/random;
- proactive disposition записывается в audit trail.

Таким образом Miyori может быть инициативной, но не назойливой: она замечает важное, ограничивает собственное внимание и никогда не превращает инициативу в автоматическое write-действие.

## Состояние релиза 00.00.49

`00.00.49` — **NEXUS Living Presence · жизнь только из реального состояния**.

N9 добавляет спокойный presence layer, который не симулирует «характер» случайными эффектами:

- `/api/projects/{id}/nexus/presence` формирует versioned authoritative presence contract;
- режимы ограничены `ready / working / waiting / attention / recovery / degraded`;
- приоритет recovery/waiting/error определяется реальным Actions state;
- knowledge attention и failed tasks участвуют как реальные причины состояния;
- last event берётся из существующего NEXUS Event Fabric;
- frontend получает реальный локальный `miyori:interaction-state` только на время фактически отправленного chat-request;
- idle/ready не занимает экран: presence host скрыт;
- нет `Math.random`, timer-driven «дыхания», `setInterval` или keyframe-анимации;
- высокий attention может раскрыть последнее подтверждённое событие;
- contextual button ведёт в Actions, Knowledge или System в зависимости от фактической причины;
- Presence capability опубликован в NEXUS snapshot с запретом random liveness.

Такой контракт готов к будущим Voice/Desktop/Avatar: визуальное или голосовое поведение сможет подписываться на те же состояния, не изобретая собственную «эмоцию».

## Состояние релиза 00.00.49

`00.00.49` — **NEXUS Living Presence · живое состояние без симуляции жизни**.

N9 делает состояние Miyori заметным только тогда, когда это действительно полезно:

- `/api/projects/{id}/nexus/presence` выводит presence из NEXUS snapshot, Actions и Event Fabric;
- реальные режимы: ready / working / verifying / waiting / recovery / attention / degraded;
- Chat публикует локальный interaction-state только во время фактически отправленного запроса;
- ready-state визуально скрыт: интерфейс не занимает место, когда ничего не происходит;
- Knowledge attention учитывается в activity/reasons, но не перехватывает primary presence;
- waiting/recovery/error имеют приоритет над обычной работой;
- verifying является отдельным состоянием только когда tool operation реально находится в verifying;
- случайная анимация, timer-driven «жизнь» и декоративная активность запрещены контрактом;
- Presence показывается только в Chat; Actions/Knowledge/System остаются рабочими поверхностями;
- high-attention состояние может раскрыть последнее подтверждённое событие;
- UI не использует keyframe-анимаций.

## Состояние релиза 00.00.48

`00.00.48` — **NEXUS Generative UI · trusted surfaces без шума в чате**.

N7 вводит безопасный слой структурированного интерфейса поверх существующего NEXUS state:

- новый `/api/projects/{id}/nexus/surfaces` возвращает versioned surface specs;
- surface kind и component выбираются только из закрытых allowlist;
- model-authored HTML и JavaScript запрещены контрактом;
- неизвестные компоненты frontend отвергает вместо попытки их выполнить;
- renderer строит DOM через `createElement/textContent`, не вставляя backend/model data через `innerHTML`;
- доступные surfaces: status, action, progress и knowledge/result collections;
- surfaces строятся только из реальных NEXUS snapshot, Actions и Knowledge read-models;
- Chat не получает постоянные карточки: используется закрытый по умолчанию «Структурный контекст»;
- shelf обновляется только при изменении authoritative snapshot fingerprint;
- навигационные действия могут только открыть доверенный NEXUS view;
- Generative UI module в snapshot теперь `ready`, а UI contract публикует allowed components;
- исправлено расхождение version diagnostics: status/project_version синхронизированы с релизом.

Новые runtime UI-библиотеки не добавлялись: текущий TypeScript registry меньше, безопаснее и лучше подходит будущему Desktop/API boundary.

## Состояние релиза 00.00.47

`00.00.47` — **NEXUS Knowledge · память, документы и evidence без визуального шума**.

N4 превращает раздел «Знания» в отдельный рабочий орган, не смешивая разные классы данных:

- `GET /api/projects/{id}/nexus/knowledge` отдаёт единый versioned read-model, но сохраняет отдельные массивы `memory / documents / claims`;
- личная память видима между проектами согласно существующей memory-модели, проектная память остаётся изолированной;
- provenance памяти показывает источник, conversation/message и проект происхождения;
- документы показывают отдельно extraction coverage и knowledge/analysis coverage;
- exhaustive Q&A отражается фактическими question counts и coverage, без выдуманного прогресса;
- Epistemic claims показывают assessment, confidence, supports/contradictions и evidence previews с source locator/quality;
- единый поиск возвращает результаты группами, не превращая память, документы и claims в один тип;
- safe actions используют существующие endpoints: подтверждение/оспаривание памяти, verify evidence, deep document analysis и rebuild структуры;
- primary Knowledge больше не открывает Drive напрямую; Drive остаётся доступен отдельной кнопкой и через legacy navigation;
- UI использует WAI-ARIA tabs и native disclosure, provenance/evidence скрыты до раскрытия;
- Knowledge CSS намеренно спокойный: крупнее текст, нейтральные поверхности, отсутствие keyframe-анимаций и декоративного knowledge graph;
- shell показывает только количество Knowledge-проблем, требующих проверки, вместо постоянного потока технических статусов.

Новые UI-runtime библиотеки не добавлены: для текущего vanilla TS/JS клиента они не дают преимущества, достаточного для нового dependency/runtime слоя. Graph capability оставлен на будущее как опциональный drill-down, а не постоянная визуализация.

## Состояние релиза 00.00.46

`00.00.46` — **NEXUS Agents & Actions · рабочий орган управления**.

N3 переводит Actions из агрегированного dashboard в единый authoritative action contract:

- один workflow отображается одной карточкой; связанный permission не дублирует действие;
- состояния нормализованы как `planned / waiting_permission / running / verifying / recovery / completed / error / cancelled`;
- preview показывается до подтверждения write-действия;
- preflight и verification фиксируются как evidence из реального tool pipeline;
- progress для workflow показывает фактический текущий шаг, завершённые шаги и бюджет, без выдуманного процента;
- result/error и история workflow/task/audit остаются доступны после завершения;
- recovery использует существующие workflow/recovery endpoints, новый engine не создавался;
- состояние `verifying` сохраняется в tool operation и переводится в recovery после аварийного рестарта;
- Action Center читает один `/api/projects/{id}/nexus/actions` вместо ручного объединения пяти независимых запросов;
- исправлена семантика NEXUS badges: permission внутри workflow больше не считается дважды, Chat не показывает «готово» при error/degraded/not_connected;
- настроенный AI считается готовым по конфигурации, а отсутствие live health-check явно остаётся limitation, а не ложной деградацией.

## Состояние релиза 00.00.45

`00.00.45` — **Portable Launch Reliability · исправление запуска ZIP**.

Исправлена критическая проблема Windows ZIP-сценария: `Miyori.bat` запускал `python app.py`, но `app.py` является ASGI-модулем и не содержит `uvicorn.run(...)`. В результате процесс просто завершался, а окно могло закрыться без понятной ошибки.

Теперь запуск устроен иначе:

- `Miyori.bat` вызывает `python -m miyori.launcher`;
- launcher проверяет Python 3.10+, обязательные файлы и занятость порта;
- если Miyori уже запущена, второй сервер не создаётся;
- Uvicorn запускается через отдельный entrypoint;
- браузер открывается только после успешного ответа `/api/status`;
- диагностика и traceback сохраняются в `logs/last-startup.log`;
- при ошибке окно запуска не закрывается молча;
- несовместимые `.venv` или `runtime` пересоздаются;
- `setup-portable.ps1` принудительно включает TLS 1.2 для старого Windows PowerShell;
- добавлен `Miyori.bat --check` для проверки установки без запуска сервера;
- CI на `windows-latest` теперь собирает архив через `git archive`, распаковывает его без `.git` и реально выполняет `Miyori.bat --check`.

Это означает, что portable ZIP теперь тестируется как отдельный продуктовый сценарий, а не косвенно через Linux backend tests.

## Состояние релиза 00.00.44

`00.00.44` — **NEXUS Shell · рабочая оболочка без декоративного футуризма**.

После N0/N1 у NEXUS появились стабильные state/event contracts. N2 использует их для первой видимой оболочки, не переписывая рабочие экраны.

Primary navigation теперь состоит из пяти разделов:

- **Чат** — диалог и текущая задача;
- **Действия** — pending permissions, workflow/recovery, фоновые задачи и event stream;
- **Знания** — Documents/Drive и рабочие проекты;
- **Дом** — домашние проекты и Home foundation;
- **Система** — настройки и системные функции.

Старые экраны Miyori AI, Mobile, Account, Update и другие служебные точки не удалены: они находятся в progressive disclosure **«Дополнительно»** и используют прежние DOM ids/renderer-функции.

Actions workspace не является декоративным dashboard. Он читает реальные `permissions / workflows / tasks / nexus/events`, а кнопки подтверждения, восстановления и отмены используют существующие API и permission/recovery contracts.

Дополнительно:

- глобальный NEXUS status и navigation badges обновляются из `NexusStore`;
- project switch автоматически переподключает store;
- при новых событиях authoritative state пересинхронизируется с NEXUS snapshot;
- primary navigation поддерживает Arrow keys, Home/End и корректный `aria-current`;
- на мобильном primary navigation становится компактной горизонтальной группой;
- NEXUS CSS не содержит `@keyframes`: shell не изображает «работу», если runtime её не подтверждает;
- исправлены буквальные escaped-newline артефакты в HTML-шаблоне;
- удалена историческая третья колонка базового layout, оставшаяся после переноса inspector в chat console;
- frontend CI получил отдельный shell contract.

## Состояние релиза 00.00.43

`00.00.43` — **NEXUS State & Event Fabric · единый нервный контур**.

NEXUS теперь умеет наблюдать изменения в существующей системе без создания второй базы событий и без переписывания Workflow Engine.

- `GET /api/projects/{project_id}/nexus/events` объединяет существующие `audit_events`, `workflow_events` и `task_events` в единый versioned envelope;
- события остаются read-only представлением уже существующих журналов;
- project isolation сохраняется на уровне SQL joins;
- cursor устойчив к одинаковым timestamp: учитываются время, источник и исходный id;
- `tail=true` используется для быстрого initial hydrate;
- event stream не считается authoritative state: каждое событие требует resync с обычным NEXUS snapshot;
- TypeScript `NexusStore` реализует hydrate, incremental sync, deduplication, bounded history и snapshot resync;
- store пока не управляет legacy UI автоматически — визуальная миграция будет отдельным этапом NEXUS Shell;
- frontend CI теперь исполняет отдельный state-store contract test.

Это фундамент для будущих Desktop, Voice, Agents, Home и Generative UI: все клиенты смогут получать одинаковое состояние и одинаковые системные события, не изобретая собственную модель истины.

## Состояние релиза 00.00.42

`00.00.42` — **NEXUS Foundation · контракты состояния и безопасная эволюция UI**.

Перед изменениями проведён полный аудит текущего проекта относительно спецификации. MIYORI NEXUS внедряется не как второй декоративный интерфейс, а как совместимый state/UI layer поверх уже работающих Chat, Memory, Documents, Agents, Home и системных модулей.

Первый этап намеренно не переписывает существующий frontend:

- существующий `GET /api/projects/{project_id}/nexus` сохранён и расширен versioned-контрактом;
- legacy-поля `project / counts / suggestions / epistemic` остаются доступными текущему classic JS;
- введены единые состояния `disabled / not_connected / ready / processing / degraded / error`;
- состояния строятся из реальных runtime-данных, а отсутствующие Voice/Desktop/Generative UI не изображаются как работающие;
- добавлен TypeScript island в `frontend/nexus/` без big-bang миграции восьми существующих JS-модулей;
- Generative UI получает typed boundary `status / progress / action / source / collection`; произвольный HTML/JavaScript от модели запрещён;
- добавлен общий accessibility runtime для modal overlays: initial focus, Tab trap, Escape и возврат focus;
- добавлены `:focus-visible` и `prefers-reduced-motion` правила;
- GitHub Actions теперь отдельно проверяет TypeScript strict typecheck, frontend build, accessibility contract и актуальность committed build artifacts;
- архитектурный аудит и дальнейший план N0–N8 зафиксированы в `docs/MIYORI_NEXUS_ARCHITECTURE.md`.

Ключевой принцип NEXUS: новая визуальная поверхность допускается только тогда, когда у неё есть реальный источник состояния или события. Декоративная «активность» не считается функциональностью.

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
- Agent Core v2.5 с model-assisted Planner, deterministic fallback и NEXUS state contract;
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
- `miyori/nexus.py` — versioned NEXUS snapshot и единые operational states для UI/будущих клиентов;
- `miyori/nexus_events.py` — read-only unified event envelope поверх audit/workflow/task journals;
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
- `miyori/launcher.py` — Windows/ZIP launcher, preflight, Uvicorn startup, readiness/browser и startup diagnostics;
- `miyori/updater.py` / `portable_updater.py` — обновление;
- `miyori/module_registry.py` — версии модулей и changelog.

### Frontend: legacy-compatible + NEXUS TypeScript island

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

С `00.00.42` рядом с legacy runtime существует отдельный NEXUS island:

- `frontend/nexus/*.ts` — TypeScript contracts, API client, accessibility runtime, state store и shell controller;
- `static/js/nexus/*.js` — собранные browser ES modules;
- `static/css/nexus.css` — только функциональный accessibility/motion layer;
- `tsconfig.nexus.json` — strict TypeScript contract;
- `scripts/check-nexus-a11y.mjs` — статический accessibility gate.

Classic JS не удаляется, пока соответствующая функция не перенесена, не проверена и не имеет совместимого API/state contract.

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

Поддерживается Python **3.10+**. Launcher использует совместимый bundled runtime, затем локальную `.venv`, затем системный Python; если подходящего Python нет, portable Python подготавливается через `setup-portable.ps1`.

Фактический серверный entrypoint:

```bat
python -m miyori.launcher
```

Для диагностики без запуска сервера:

```bat
Miyori.bat --check
```

При проблеме запуска смотрите:

```text
logs\last-startup.log
```

Launcher проверяет обязательные файлы, порт, существующий процесс Miyori и импорт ASGI-приложения. Uvicorn запускается только после успешного preflight, а браузер открывается только после готовности `/api/status`.

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

Отдельный `portable_zip` job на Windows:

- создаёт ZIP через `git archive` без `.git`;
- распаковывает архив в чистую временную папку;
- запускает `Miyori.bat --check`;
- проверяет реальный Windows bootstrap, создание `.venv`, зависимости и launcher preflight.

Отдельный frontend job выполняет:

- TypeScript `strict` typecheck;
- сборку NEXUS ES modules;
- accessibility contract;
- исполняемый NEXUS state-store contract;
- NEXUS shell contract: пять разделов, live-status semantics, progressive disclosure, keyboard contract и запрет decorative keyframes;
- синтаксическую проверку classic JS и NEXUS modules;
- `git diff --exit-code -- static/js/nexus`, чтобы committed build не расходился с TypeScript source.

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
- `00.00.41` — Extraction Integrity: source extraction coverage + Office/PDF completeness manifest + truthful exhaustive coverage;
- `00.00.42` — NEXUS Foundation: versioned state contract + TypeScript island + typed Generative UI boundary + accessibility/frontend CI;
- `00.00.43` — NEXUS State & Event Fabric: unified read-only event envelope + cursor/tail + client store + authoritative snapshot resync;
- `00.00.44` — NEXUS Shell: Chat / Actions / Knowledge / Home / System + operational Actions workspace + state-driven badges + keyboard/mobile navigation;
- `00.00.45` — Portable Launch Reliability: real Uvicorn launcher + Python preflight + startup log + Windows ZIP CI.

Канонический changelog приложения доступен через `miyori/module_registry.py` и API manifest/changelog.
