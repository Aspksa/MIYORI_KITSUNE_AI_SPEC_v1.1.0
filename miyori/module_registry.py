from __future__ import annotations

PROJECT_VERSION = "00.00.49"

MODULES = {
    "miyori_ai": {
        "name": "Miyori Kitsune AI",
        "version": "2.7.0",
        "status": "active",
        "description": "AI Core v2.7: NEXUS Action Contract поверх persistent workflows, permission/preflight/verification/recovery, Document Intelligence и проверяемой памяти.",
    },
    "workflow_engine": {
        "name": "Workflow Engine",
        "version": "1.2.0",
        "status": "active",
        "description": "Persistent workflow state, permission continuation, explicit verifying state, tool operations, crash recovery, idempotency и audit trail.",
    },
    "account": {
        "name": "Личный кабинет",
        "version": "1.2.0",
        "status": "active",
        "description": "Профиль владельца, Cloud.ru, аватар, устройства и сессии.",
    },
    "mobile": {
        "name": "Мобильное приложение",
        "version": "0.1.0",
        "status": "planned",
        "description": "Подготовленный раздел будущего мобильного клиента и привязки устройств.",
    },
    "nexus": {
        "name": "MIYORI NEXUS",
        "version": "0.7.0",
        "status": "active",
        "description": "NEXUS Living Presence: authoritative runtime presence поверх Actions/Knowledge/Event Fabric и реального chat interaction state; idle остаётся тихим.",
    },
    "settings": {
        "name": "Настройки",
        "version": "0.4.1",
        "status": "active",
        "description": "Системные параметры Miyori и состояние локальных компонентов.",
    },
    "drive": {
        "name": "Документы / Облако / Miyori",
        "version": "1.8.0",
        "status": "active",
        "description": "Miyori Drive: оригиналы, extraction integrity, структура документов, безопасная корзина, Document Intelligence, поиск и RAG.",
    },
    "document_intelligence": {
        "name": "Document Intelligence",
        "version": "1.2.0",
        "status": "active",
        "description": "Структурное понимание, extraction integrity и exhaustive Q&A: отдельное покрытие оригинала и AI, evidence, recovery и synthesis.",
    },
    "projects": {
        "name": "Проекты",
        "version": "0.8.0",
        "status": "active",
        "description": "Рабочие и домашние пространства с отдельными проектными модулями.",
    },
    "primavtodor": {
        "name": "АО «Примавтодор»",
        "version": "0.6.0",
        "status": "active",
        "description": "Отдельный рабочий проект с модулями Табель, Гараж и Сотрудники.",
    },
    "primavtodor_timesheet": {
        "name": "Примавтодор · Табель",
        "version": "0.1.0",
        "status": "foundation",
        "description": "Основа модуля учёта табелей, смен и рабочего времени.",
    },
    "primavtodor_garage": {
        "name": "Примавтодор · Гараж",
        "version": "0.1.0",
        "status": "foundation",
        "description": "Основа модуля техники, транспорта и гаражного учёта.",
    },
    "primavtodor_employees": {
        "name": "Примавтодор · Сотрудники",
        "version": "0.2.0",
        "status": "active",
        "description": "База сотрудников с ФИО, отделом, должностью и номером топливной карты.",
    },
    "primavtodor_counterparties": {
        "name": "Примавтодор · Контрагенты",
        "version": "0.1.0",
        "status": "active",
        "description": "Контрагенты проекта: реквизиты, контакты и связанные документы.",
    },
    "primavtodor_contracts": {
        "name": "Примавтодор · Договоры",
        "version": "0.1.0",
        "status": "active",
        "description": "Реестр договоров проекта и связанное файловое пространство.",
    },
    "primavtodor_invoice_offers": {
        "name": "Примавтодор · Счёт-Оферта",
        "version": "0.1.0",
        "status": "active",
        "description": "Счета-оферты: счёт с краткими существенными условиями договора.",
    },
    "home_network": {
        "name": "Домашняя сеть",
        "version": "0.1.0",
        "status": "active",
        "description": "Домашние устройства, адреса, состояние и заметки.",
    },
    "parental_control": {
        "name": "Детский контроль Miyori",
        "version": "0.1.0",
        "status": "foundation",
        "description": "Прозрачные правила для подключённого телефона: лимит времени, ночной режим и категории ограничений.",
    },
    "rag": {
        "name": "RAG Core",
        "version": "1.2.0",
        "status": "active",
        "description": "Hybrid FTS5 + lexical retrieval + Document Intelligence, память и проверенные знания.",
    },
    "epistemic": {
        "name": "Epistemic Core",
        "version": "1.1.0",
        "status": "active",
        "description": "Утверждения, источники, evidence, противоречия и верификация знаний.",
    },
    "persona": {
        "name": "Persona Pack",
        "version": "2.0.0",
        "status": "active",
        "description": "Каноническая личность Miyori Kitsune и правила поведения.",
    },
    "launcher": {
        "name": "Portable Launcher",
        "version": "1.0.0",
        "status": "active",
        "description": "Надёжный Windows/ZIP запуск: Python preflight, Uvicorn entrypoint, readiness/browser, startup log и CI-проверка portable-архива.",
    },
    "updater": {
        "name": "Обновление проекта",
        "version": "1.2.1",
        "status": "active",
        "description": "Git fast-forward и Portable ZIP updater с резервными копиями и проверкой GitHub.",
    },
}

RELEASES = [
    {
        "version": "00.00.49",
        "title": "NEXUS Living Presence · реальное состояние без симуляции",
        "summary": "N9 добавляет versioned Living Presence поверх snapshot/actions/events и реального chat request state. Idle скрыт, activity не симулируется, а waiting/verifying/recovery/error показываются только из фактических runtime states.",
        "modules": [
            {
                "key": "nexus",
                "version": "0.7.0",
                "changes": [
                    "Добавлен /api/projects/{project_id}/nexus/presence.",
                    "Presence различает working, verifying, waiting, recovery, attention и degraded по реальному runtime state.",
                    "Chat request lifecycle публикует interaction-state вместо декоративного thinking timer.",
                    "Ready Presence скрывается и не создаёт постоянный визуальный шум.",
                    "Knowledge attention не меняет primary Presence, а остаётся фоновым сигналом.",
                    "Случайная/таймерная анимация запрещена source contract и UI contract tests."
                ],
            },
        ],
    },
    {
        "version": "00.00.49",
        "title": "NEXUS Living Presence · реальная активность без имитации",
        "summary": "N9 вводит versioned presence contract и компактный event-driven UI: Miyori показывает работу, ожидание, recovery или attention только при наличии реального runtime/event source.",
        "modules": [
            {
                "key": "nexus",
                "version": "0.7.0",
                "changes": [
                    "Добавлен /api/projects/{project_id}/nexus/presence с authoritative source contract.",
                    "Presence modes derived из Actions, Knowledge, failed tasks и Event Fabric.",
                    "Chat публикует thinking только пока фактически выполняется отправленный запрос.",
                    "Ready/idle полностью скрывается, чтобы не создавать постоянный визуальный шум.",
                    "Presence navigation ведёт в Actions/Knowledge/System по типу реальной причины.",
                    "Random liveness, timer animation и декоративная симуляция активности запрещены."
                ],
            },
        ],
    },
    {
        "version": "00.00.48",
        "title": "NEXUS Generative UI · trusted surfaces",
        "summary": "N7 добавляет versioned surface contract и закрытый TypeScript renderer registry. Модель не получает права генерировать HTML/JS; contextual UI строится только из реального NEXUS state и по умолчанию не мешает Chat.",
        "modules": [
            {
                "key": "nexus",
                "version": "0.6.0",
                "changes": [
                    "Добавлен /api/projects/{project_id}/nexus/surfaces.",
                    "Surface specs ограничены allowlist kind/component и policy model_html_allowed=false, script_allowed=false.",
                    "Frontend renderer использует createElement/textContent и отклоняет неизвестные компоненты.",
                    "Chat получил закрытый по умолчанию quiet surface shelf вместо постоянных карточек.",
                    "Surface refresh привязан к authoritative NEXUS snapshot fingerprint.",
                    "Generative UI module переведён в ready; ui_contract публикует разрешённые surface components."
                ],
            },
        ],
    },
    {
        "version": "00.00.47",
        "title": "NEXUS Knowledge · provenance, evidence и coverage без шума",
        "summary": "N4 вводит отдельный Knowledge Contract и спокойный рабочий интерфейс: Memory, Documents и Epistemic остаются разными сущностями, но получают общий поиск, provenance/evidence navigation, coverage, safe actions и progressive disclosure.",
        "modules": [
            {
                "key": "nexus",
                "version": "0.5.0",
                "changes": [
                    "Добавлен versioned /api/projects/{project_id}/nexus/knowledge с отдельными memory/documents/claims секциями.",
                    "Knowledge primary view больше не является прямым алиасом Drive; Drive сохранён как отдельная файловая поверхность.",
                    "Memory показывает scope/kind/provenance и корректно маршрутизирует действия к проекту происхождения user-memory.",
                    "Documents показывают extraction coverage, analysis coverage, parser provenance и exhaustive Q&A coverage.",
                    "Epistemic claims показывают evidence preview, source locator/quality, supports/contradictions и verify action.",
                    "Поиск работает сразу по трём слоям, но возвращает группированные результаты без смешивания типов.",
                    "Tabs/disclosure следуют accessibility semantics; декоративные анимации и постоянный knowledge graph не добавлены."
                ],
            },
        ],
    },
    {
        "version": "00.00.46",
        "title": "NEXUS Agents & Actions · рабочий орган управления",
        "summary": "N3 вводит единый action contract поверх существующего Workflow Engine: workflow, permission, tool operation и background task отображаются без дублирования, с реальными preview, verifying, evidence, recovery, result и history состояниями.",
        "modules": [
            {
                "key": "nexus",
                "version": "0.4.0",
                "changes": [
                    "Добавлен versioned /api/projects/{project_id}/nexus/actions как единый read model для Action Center.",
                    "Permission, принадлежащий workflow, встраивается в карточку workflow и не считается вторым действием.",
                    "UI различает planned, waiting_permission, running, verifying, recovery, completed, error и cancelled.",
                    "Preview, preflight/verification evidence, workflow steps, result/error и history идут из persisted runtime state.",
                    "Actions workspace больше не склеивает пять независимых API-ответов на клиенте.",
                    "Исправлены двойной action badge и ложное «готово» Chat при degraded/error/not_connected."
                ],
            },
            {
                "key": "workflow_engine",
                "version": "1.2.0",
                "changes": [
                    "Tool operation получил persisted verifying state.",
                    "Verification failure переводит операцию в recovery_required вместо зависания.",
                    "Interrupted verifying operation участвует в startup recovery так же, как running."
                ],
            },
        ],
    },
    {
        "version": "00.00.45",
        "title": "Portable Launch Reliability · исправление запуска ZIP",
        "summary": "Исправлена критическая проблема portable-сценария: Miyori.bat запускал app.py, который только объявляет FastAPI-приложение и не стартует Uvicorn. Добавлен отдельный launcher, проверки Python/порта/файлов, startup log и Windows CI, который реально собирает ZIP без .git и выполняет Miyori.bat --check.",
        "modules": [
            {
                "key": "launcher",
                "version": "1.0.0",
                "changes": [
                    "Miyori.bat больше не запускает app.py напрямую; сервер стартует через python -m miyori.launcher.",
                    "Launcher выполняет preflight, проверяет занятый порт и уже запущенную Miyori, стартует Uvicorn и открывает браузер только после readiness /api/status.",
                    "Все startup-сообщения и traceback сохраняются в logs/last-startup.log.",
                    "Miyori.bat требует Python 3.10+; несовместимые .venv/runtime автоматически пересоздаются.",
                    "Добавлен Miyori.bat --check для воспроизводимой диагностики без запуска сервера.",
                    "setup-portable.ps1 принудительно включает TLS 1.2 для Windows PowerShell 5.1 и валидирует загруженный Python.",
                    "Ошибки pip больше не скрываются quiet-режимом, а окно запуска не закрывается молча при сбое.",
                    "GitHub Actions получил Windows portable_zip job: git archive → Expand-Archive → Miyori.bat --check."
                ],
            },
        ],
    },
    {
        "version": "00.00.44",
        "title": "NEXUS Shell · рабочая оболочка без декоративного футуризма",
        "summary": "Первый видимый слой MIYORI NEXUS построен поверх уже проверенных state/event contracts: пять стабильных разделов Chat / Actions / Knowledge / Home / System, операционный Actions workspace, реальные status badges, keyboard navigation и responsive shell. Legacy renderers сохранены и используются через совместимый bridge.",
        "modules": [
            {
                "key": "nexus",
                "version": "0.3.0",
                "changes": [
                    "Primary navigation сокращена до пяти устойчивых разделов вместо набора равнозначных технических пунктов.",
                    "Добавлен Actions workspace для pending permissions, active/recovering workflows, фоновых задач и последних NEXUS events.",
                    "Badges и глобальный status читаются из NexusStore/NEXUS snapshot, а не вычисляются декоративно на клиенте.",
                    "Старые Documents, Home, Settings, Account, Mobile и Update renderers не переписаны; shell вызывает их через совместимый bridge.",
                    "Secondary функции перенесены в progressive disclosure «Дополнительно», без удаления старых DOM ids и обработчиков.",
                    "Добавлена keyboard navigation Arrow/Home/End и mobile horizontal primary nav.",
                    "NEXUS shell CSS не содержит keyframe-анимаций; состояния передаются текстом, цветом и реальными счётчиками.",
                    "Frontend CI дополнен отдельным NEXUS shell contract test."
                ],
            },
        ],
    },
    {
        "version": "00.00.43",
        "title": "NEXUS State & Event Fabric · единый нервный контур",
        "summary": "NEXUS получил versioned read-only event fabric поверх существующих audit/workflow/task журналов и типизированный клиентский store с cursor/resync. Источники данных не переписываются: event stream сообщает об изменениях, а authoritative state по-прежнему берётся из NEXUS snapshot.",
        "modules": [
            {
                "key": "nexus",
                "version": "0.2.0",
                "changes": [
                    "Добавлен /api/projects/{project_id}/nexus/events с единым envelope для audit_events, workflow_events и task_events.",
                    "Cursor использует created_at + source rank + source id и не теряет события с одинаковым временем.",
                    "tail=true даёт быстрый initial hydrate без перечитывания всей истории.",
                    "Каждое событие помечено requires_resync: UI не вычисляет authoritative state из event stream.",
                    "Добавлен NexusStore: hydrate, incremental sync, deduplication, bounded history и snapshot resync после новых событий.",
                    "Новый store не подключён к legacy UI автоматически: визуальная миграция откладывается до NEXUS Shell."
                ],
            },
            {
                "key": "miyori_ai",
                "version": "2.6.0",
                "changes": [
                    "Существующие task/workflow/audit журналы объединяются read-only адаптером без миграции или дублирования данных.",
                    "Project isolation применяется к event stream на уровне SQL joins.",
                    "Frontend CI дополнен исполняемым контрактным тестом NEXUS state store."
                ],
            },
        ],
    },
    {
        "version": "00.00.42",
        "title": "NEXUS Foundation · контракты состояния и безопасная эволюция UI",
        "summary": "Начато постепенное внедрение MIYORI NEXUS без переписывания рабочего интерфейса: существующий /nexus превращён в versioned state contract, добавлен TypeScript island, typed Generative UI boundary, accessibility runtime и отдельный frontend CI gate.",
        "modules": [
            {
                "key": "nexus",
                "version": "0.1.0",
                "changes": [
                    "Добавлен отдельный miyori/nexus.py как server-side агрегатор фактического состояния проекта.",
                    "Состояния нормализованы по контракту disabled / not_connected / ready / processing / degraded / error.",
                    "Legacy поля counts, suggestions и epistemic сохранены для совместимости текущего classic JS.",
                    "Будущие Voice, Desktop и Generative UI отображаются как реально недоступные capability, а не имитируются интерфейсом.",
                    "Generative UI boundary разрешает только типизированные status/progress/action/source/collection surfaces; произвольный model HTML запрещён."
                ],
            },
            {
                "key": "miyori_ai",
                "version": "2.5.0",
                "changes": [
                    "Зафиксирован архитектурный аудит относительно полной спецификации и roadmap N0–N8.",
                    "NEXUS развивается поверх существующих Memory, Documents, Agents, Home и Epistemic API без big-bang rewrite.",
                    "Provider configuration отделён от фактического health: настроенная модель не маркируется как безусловно ready без сетевой проверки."
                ],
            },
            {
                "key": "settings",
                "version": "0.4.1",
                "changes": [
                    "Добавлен общий accessibility runtime для существующих modal overlays: initial focus, Tab trap, Escape и возврат focus.",
                    "Добавлены focus-visible и prefers-reduced-motion правила без декоративной анимации."
                ],
            },
        ],
    },
    {
        "version": "00.00.41",
        "title": "Extraction Integrity · честная полнота чтения оригинала",
        "summary": "Miyori теперь отдельно измеряет полноту извлечения данных из оригинального файла и полноту AI-анализа уже извлечённого текста. Это исключает ложное «100% понимание», если PDF, презентация или Office-файл содержит непрочитанные страницы, изображения, диаграммы или другие визуальные объекты.",
        "modules": [
            {
                "key": "document_intelligence",
                "version": "1.2.0",
                "changes": [
                    "Добавлены extraction_status, extraction_coverage, extraction_warnings и extraction_details.",
                    "PDF считает покрытие по страницам с доступным текстовым слоем и явно отмечает страницы, которым нужен OCR.",
                    "DOCX дополнительно извлекает headers/footers и текст footnotes/endnotes/comments; изображения и диаграммы фиксируются как непроанализированная визуальная часть.",
                    "XLSX сохраняет формулы даже при отсутствии cached value и считает изображения/диаграммы.",
                    "PPTX учитывает слайды без текста, speaker notes, media и charts.",
                    "Parser version повышен до 1.1.0; старые базы обновляются in-place."
                ],
            },
            {
                "key": "drive",
                "version": "1.8.0",
                "changes": [
                    "Экран понимания показывает две независимые шкалы: извлечение из оригинала и AI-анализ извлечённого текста.",
                    "Предупреждения extraction manifest видны пользователю непосредственно в карточке документа.",
                    "Exhaustive Q&A показывает scan/original/overall coverage вместо одного неоднозначного процента."
                ],
            },
            {
                "key": "miyori_ai",
                "version": "2.4.0",
                "changes": [
                    "Document Intelligence tools возвращают extraction status/coverage/warnings вместе с AI coverage.",
                    "Если оригинал извлечён частично, exhaustive-ответ автоматически получает caveat и не может выдавать отсутствие факта как доказанное для всего оригинала.",
                    "Confidence полного вопроса понижается при неполном извлечении исходного файла.",
                    "Development Self-Check отдельно контролирует extraction integrity."
                ],
            },
        ],
    },
    {
        "version": "00.00.40",
        "title": "Exhaustive Document Q&A · проверка всего документа по вопросу",
        "summary": "Добавлен отдельный режим полной проверки: конкретный вопрос проходит через все окна извлечённого текста, а итоговый ответ строится только из сохранённых evidence с locator-ами. RAG/top-K больше не используется как доказательство того, что проверена вся книга.",
        "modules": [
            {
                "key": "document_intelligence",
                "version": "1.1.0",
                "changes": [
                    "Добавлены persistent document_questions и document_question_windows.",
                    "Каждый полный вопрос сканирует все окна документа и отдельно считает coverage_ratio.",
                    "Нерелевантные окна тоже отмечаются как проверенные; отсутствие совпадения не означает пропуск окна.",
                    "Итоговый ответ синтезируется только из evidence/answer_fragment, найденных при полном проходе.",
                    "Каждое evidence ограничено по размеру и сохраняет locator; внешний контекст модели запрещён.",
                    "После сбоя уже проверенные окна переиспользуются по SHA-256 fingerprint содержимого.",
                    "Fingerprint также усилен для обычного глубокого анализа документа."
                ],
            },
            {
                "key": "drive",
                "version": "1.7.0",
                "changes": [
                    "В «Понимании документа» появился режим «Спросить по всему документу».",
                    "Показываются отдельный статус вопроса, фактическое покрытие, ответ и доказательства с locator-ами.",
                    "Одинаковый вопрос к неизменному оригиналу переиспользует готовый или уже выполняющийся run.",
                    "Полные вопросы выполняются фоново и не блокируют браузер."
                ],
            },
            {
                "key": "miyori_ai",
                "version": "2.3.0",
                "changes": [
                    "В архитектуре явно разделены быстрый retrieval и exhaustive verification.",
                    "Top-K RAG предназначен для обычных быстрых ответов; утверждение «проверен весь документ» допустимо только для exhaustive run с полным coverage.",
                    "Agent Core получил инструменты project_document_exhaustive_question и project_document_question_status для запуска и чтения полного прохода из чата.",
                    "Полные проверки записываются в Audit Trail как отдельные document.question события."
                ],
            },
        ],
    },
    {
        "version": "00.00.39",
        "title": "Document Intelligence · полное понимание документов и книг",
        "summary": "Miyori перестала воспринимать длинный документ как набор несвязанных чанков: добавлены структурный parser, persistent document graph, hierarchical map-reduce анализ всего извлечённого текста, coverage tracking, глубокий поиск, Agent tools и интерфейс понимания в Miyori Drive.",
        "modules": [
            {
                "key": "document_intelligence",
                "version": "1.0.0",
                "changes": [
                    "Добавлен отдельный persistent слой document_intelligence, document_nodes и document_analysis_windows.",
                    "TXT/Markdown получают иерархию заголовков и строковые locator-ы; DOCX — стили заголовков, параграфы и таблицы; PDF — страницы и структурные блоки; XLSX — листы и диапазоны строк; PPTX — слайды; JSON — JSON-path блоки.",
                    "Локальная структурная карта создаётся сразу при загрузке оригинала и не зависит от доступности Cloud.ru.",
                    "Глубокий анализ проходит весь извлечённый текст последовательно по окнам и затем сводит результаты многоуровневым synthesis.",
                    "coverage_ratio показывает фактическую долю текста, прошедшую AI-анализ; статус complete возможен только при практически полном покрытии.",
                    "Каждый вывод сохраняет locator к месту документа; анализ не должен дополнять документ внешними знаниями.",
                    "После сбоя уже обработанные окна переиспользуются, если границы и locator-ы совпадают."
                ],
            },
            {
                "key": "drive",
                "version": "1.6.0",
                "changes": [
                    "В карточке файла появилась команда «Понимание документа».",
                    "Экран показывает слова, страницы, разделы, структурные узлы, coverage, outline, целостную сводку, ключевые пункты, риски и сущности.",
                    "Полный анализ книги запускается как фоновая задача; оригинал остаётся доступен независимо от результата анализа.",
                    "Для PDF без текстового слоя сохраняется статус needs_ocr вместо ложного заявления о полном понимании."
                ],
            },
            {
                "key": "miyori_ai",
                "version": "2.2.0",
                "changes": [
                    "Добавлены read-tools project_document_understanding, project_document_outline и project_document_deep_search.",
                    "Planner может выбирать между обычным чтением чанков и структурным разбором целого документа.",
                    "Source manifest сохраняет ссылку на оригинал и locator для ответов, основанных на Document Intelligence."
                ],
            },
            {
                "key": "rag",
                "version": "1.2.0",
                "changes": [
                    "Document Intelligence стал отдельным retrieval-каналом с приоритетом структурных совпадений.",
                    "Глобальная сводка и релевантные структурные узлы объединяются с FTS/lexical чанками через существующий RRF-контур."
                ],
            },
            {
                "key": "workflow_engine",
                "version": "1.1.0",
                "changes": [
                    "Running background tasks после перезапуска возвращаются в очередь; отменённые задачи фиксируются как cancelled.",
                    "Document Intelligence progress сохраняется по окнам и может безопасно продолжаться после сбоя."
                ],
            },
        ],
    },
    {
        "version": "00.00.38",
        "title": "AI Reliability & Workflow Engine",
        "summary": "Agent Core получил устойчивое состояние workflow, продолжение после разрешений, idempotency, Tool Registry v2, audit trail, crash recovery, verify-before-write и интеграционный контур тестирования.",
        "modules": [
            {
                "key": "miyori_ai",
                "version": "2.1.0",
                "changes": [
                    "Каждый инструментальный запрос получает persistent workflow в SQLite и переживает перезапуск приложения.",
                    "После решения permission тот же workflow продолжается с сохранённой историей, а не планируется заново.",
                    "Chat request_id и response_key защищают от повторных HTTP-запросов и дублирования сообщений.",
                    "Добавлены состояния running / waiting_permission / recovering / completed / failed / cancelled.",
                    "Добавлены API просмотра, восстановления и отмены workflow."
                ],
            },
            {
                "key": "workflow_engine",
                "version": "1.0.0",
                "changes": [
                    "Добавлены workflow_steps, workflow_events, tool_operations и audit_events.",
                    "Tool operations получают стабильный idempotency key и preflight snapshot.",
                    "Crash recovery сначала проверяет фактическое состояние и только потом допускает безопасный retry.",
                    "Verify-before-write блокирует изменение, если данные изменились после подтверждения пользователя.",
                    "Audit Trail фиксирует запрос, решение Planner, permission, фактическое выполнение и завершение workflow.",
                    "Recovery-состояния включены в Development Self-Check."
                ],
            },
            {
                "key": "drive",
                "version": "1.5.1",
                "changes": [
                    "Создание папок и перемещение документов получили preflight/verify и crash-safe idempotent execution.",
                    "Конфликт между подтверждением и фактическим состоянием Drive не перезаписывается автоматически."
                ],
            },
        ],
    },
    {
        "version": "00.00.37",
        "title": "Miyori AI Core v2",
        "summary": "Новый контур принятия решений: Context Router, model-assisted Planner с deterministic fallback, пошаговый Agent Core, глубокая интеграция с Miyori Drive, сохраняемые источники ответов, многослойная память, человекочитаемая эпистемическая оценка и расширенный тестовый контур.",
        "modules": [
            {
                "key": "miyori_ai",
                "version": "2.0.0",
                "changes": [
                    "Добавлен Context Router: запрос получает только релевантные память, документы, знания и инструменты.",
                    "Agent Core переведён с keyword-only выбора на model-assisted Planner loop до 5 шагов с deterministic fallback.",
                    "Planner использует строгий JSON-контракт и не может выбирать инструменты вне registry.",
                    "Write-действия Planner не обходят permission layer: выполнение останавливается до явного подтверждения.",
                    "Источники рабочих документов сохраняются вместе с сообщением и отображаются при повторном открытии разговора."
                ],
            },
            {
                "key": "drive",
                "version": "1.5.0",
                "changes": [
                    "Добавлены AI-инструменты каталога и чтения документов текущего проекта.",
                    "Добавлены безопасные write-инструменты создания папки и перемещения документа через permission layer.",
                    "Ответы Miyori получают стабильные ссылки на оригиналы документов Drive."
                ],
            },
            {
                "key": "rag",
                "version": "1.1.0",
                "changes": [
                    "Retrieval получил управляемые каналы documents / user memory / project memory / epistemic knowledge.",
                    "Context Router может полностью исключать ненужные каналы из текущего запроса."
                ],
            },
            {
                "key": "epistemic",
                "version": "1.1.0",
                "changes": [
                    "Добавлены оценки Подтверждено / Вероятно / Есть противоречия / Недостаточно данных.",
                    "Противоречия дополнительно выявляются по несовместимым числовым значениям при достаточном смысловом пересечении."
                ],
            },
        ],
    },
    {
        "version": "00.00.36",
        "title": "Miyori Drive · рабочие документы и безопасное хранение",
        "summary": "Miyori Drive перенесён в физическую папку каждого проекта. Папки из браузера создаются на диске, оригиналы сохраняются локально, удаление стало мягким с корзиной и восстановлением, а удалённые документы исключаются из RAG.",
        "modules": [
            {
                "key": "drive",
                "version": "1.4.0",
                "changes": [
                    "Для каждого проекта создаётся отдельное хранилище «Документы - Облако - Miyori» внутри data/workspace/<project_id>.",
                    "Структура папок Drive отражается в физической файловой системе проекта.",
                    "Загрузка через браузер сохраняет байт-в-байт оригинал документа.",
                    "Удаление файла или папки перемещает оригинал в локальную корзину вместо безвозвратного стирания.",
                    "Добавлено восстановление файлов и папок из корзины.",
                    "Документы из корзины исключаются из поиска и RAG-индекса.",
                    "Добавлено скачивание оригинала и поиск по содержимому документов в разделе «Знания Miyori».",
                    "Старые оригиналы из data/documents/<project_id> безопасно копируются в новую структуру при синхронизации."
                ],
            },
            {
                "key": "rag",
                "version": "1.0.0",
                "changes": [
                    "RAG индексирует только активные документы и игнорирует содержимое корзины."
                ],
            },
        ],
    },
    {
        "version": "00.00.35",
        "title": "Frontend Cleanup & Architecture",
        "summary": "Синхронизирована документация, монолитные frontend-ресурсы разделены на упорядоченные модули, удалён оставшийся legacy-код визуализации внутренних этапов обработки. Пользовательское поведение релиза 00.00.34 сохранено.",
        "modules": [
            {
                "key": "miyori_ai",
                "version": "1.1.2",
                "changes": [
                    "Удалены пустой setProcessingStage, таймеры и вызовы скрытой processing-визуализации.",
                    "Монолит static/app.js разделён на core, data, chat, workspace, drive, projects, settings и boot без изменения порядка выполнения.",
                ],
            },
            {
                "key": "settings",
                "version": "0.4.1",
                "changes": [
                    "Монолит static/style.css разделён на foundation, chat, workspace, drive, modules, modes и audit.",
                    "Удалены неиспользуемые processing selectors, keyframes и страховочные legacy overrides.",
                ],
            },
        ],
    },
    {
        "version": "00.00.34",
        "title": "Полный аудит веб-интерфейса и домашние модули",
        "summary": "Убрана визуализация этапов обработки, нормализована типографика и ширина чата, исправлена адаптивность. В домашнее пространство добавлены Домашняя сеть и Детский контроль Miyori.",
        "modules": [
            {
                "key": "miyori_ai",
                "version": "1.1.2",
                "changes": [
                    "Полностью удалена визуализация Пишет текст / Запрос / Контекст / Работа / Результат.",
                    "Чат сужен до комфортной рабочей колонки; увеличены текст сообщений и элементы управления.",
                ],
            },
            {
                "key": "settings",
                "version": "0.4.1",
                "changes": [
                    "Добавлен общий audit-layer типографики и адаптивности для форм, workspace, таблиц и мобильного представления.",
                ],
            },
            {
                "key": "home_network",
                "version": "0.1.0",
                "changes": [
                    "Добавлен CRUD домашних устройств: имя, тип, адрес, статус и заметка.",
                ],
            },
            {
                "key": "parental_control",
                "version": "0.1.0",
                "changes": [
                    "Добавлены профили детского контроля: ребёнок, устройство, дневной лимит, ночной режим и категории.",
                    "Модуль не предусматривает скрытого наблюдения и рассчитан на явную привязку телефона Miyori.",
                ],
            },
        ],
    },
    {
        "version": "00.00.33",
        "title": "Чистый статус обработки и деловые модули Примавтодор",
        "summary": "Этапы обработки перенесены из бокового меню в компактный статус чата. АО «Примавтодор» связано с Miyori Drive и получило Контрагентов, Договоры и Счёт-Оферту.",
        "modules": [
            {
                "key": "miyori_ai",
                "version": "1.1.1",
                "changes": [
                    "Удалён постоянный блок «Этапы обработки» из левой панели.",
                    "В чате добавлен компактный статус: Пишет текст → Запрос принят → Сбор контекста → Работа → Результат.",
                    "Статус результата автоматически исчезает и не засоряет историю диалога.",
                ],
            },
            {
                "key": "primavtodor",
                "version": "0.6.0",
                "changes": [
                    "Проект явно связан с Miyori Drive через единый project_id.",
                    "Для деловых модулей автоматически создаются папки Контрагенты, Договоры и Счёт-Оферта.",
                ],
            },
            {
                "key": "primavtodor_counterparties",
                "version": "0.1.0",
                "changes": ["Добавлен реестр контрагентов с ИНН, КПП, адресом и контактами."],
            },
            {
                "key": "primavtodor_contracts",
                "version": "0.1.0",
                "changes": ["Добавлен реестр договоров с номером, датой, предметом, суммой и статусом."],
            },
            {
                "key": "primavtodor_invoice_offers",
                "version": "0.1.0",
                "changes": ["Добавлен реестр счётов-оферт с суммой, датой, статусом и краткими условиями договора."],
            },
        ],
    },
    {
        "version": "00.00.32",
        "title": "Системные настройки v0.4",
        "summary": "Добавлены рабочие вкладки Общие, Система, Автоматизация и Диагностика.",
        "modules": [
            {
                "key": "settings",
                "version": "0.4.0",
                "changes": [
                    "Windows autostart, открытие браузера, тема, плотность интерфейса и стартовый экран.",
                    "Системная информация: версия, установка, Python, SQLite, worker, дисковое пространство и data.",
                    "Настройка background worker и политики GitHub/Portable updater.",
                    "Self-check, версии модулей, экспорт диагностического JSON и очистка runtime/logs.",
                ],
            },
            {
                "key": "updater",
                "version": "1.2.1",
                "changes": [
                    "Portable update теперь можно отключить.",
                    "Резервные копии portable update управляются системной настройкой.",
                    "Интервал и автообновление сохраняются через системные настройки.",
                ],
            },
        ],
    },
    {
        "version": "00.00.31",
        "title": "AI Center, версии модулей и сотрудники Примавтодор",
        "summary": "Miyori Kitsune становится центром настроек AI. Добавлены версии модулей, подробный changelog и полноценная база сотрудников АО «Примавтодор».",
        "modules": [
            {
                "key": "miyori_ai",
                "version": "1.1.0",
                "changes": [
                    "Добавлен отдельный центр настроек AI вместо перехода в чат.",
                    "Добавлены стиль общения, подробность, инициативность и рабочие режимы.",
                    "Добавлены настройки RAG, подтверждённой памяти, неопределённости и следующего шага.",
                ],
            },
            {
                "key": "updater",
                "version": "1.2.0",
                "changes": [
                    "Добавлен реестр версий всех крупных модулей.",
                    "Экран обновления показывает полное описание текущего релиза и изменения по модулям.",
                    "Версии позволяют видеть, какие модули развиваются, а какие остаются foundation/planned.",
                ],
            },
            {
                "key": "primavtodor_employees",
                "version": "0.2.0",
                "changes": [
                    "Добавлена постоянная SQLite-база сотрудников.",
                    "Добавление и редактирование ФИО, отдела, должности и номера топливной карты.",
                    "Добавлено удаление сотрудников из модуля проекта.",
                ],
            },
        ],
    },
    {
        "version": "00.00.30",
        "title": "Личный кабинет и улучшенный Miyori Drive",
        "summary": "Профиль владельца, Cloud.ru, устройства и drag-and-drop файловое пространство.",
        "modules": [
            {"key": "account", "version": "1.2.0", "changes": ["Профиль владельца, аватар, Cloud.ru, устройства и сессии."]},
            {"key": "drive", "version": "1.3.0", "changes": ["Drag-and-drop, статистика файлов, поиск, плитка/список и RAG."]},
        ],
    },
    {
        "version": "00.00.29",
        "title": "Miyori Drive",
        "summary": "Файловый менеджер в стиле современного облачного диска.",
        "modules": [
            {"key": "drive", "version": "1.2.0", "changes": ["Мои файлы, Недавние, поиск, плитка/список, вложенные папки."]},
        ],
    },
    {
        "version": "00.00.28",
        "title": "Надёжная доставка статики",
        "summary": "Исправлен stale cache после portable-обновлений.",
        "modules": [
            {"key": "updater", "version": "1.1.0", "changes": ["Cache-busting app.js/style.css и Cache-Control no-store."]},
        ],
    },
    {
        "version": "00.00.27",
        "title": "Office/PDF и модули Примавтодор",
        "summary": "Добавлен ingestion PDF, DOCX, XLSX, PPTX и проектные модули Табель, Гараж, Сотрудники.",
        "modules": [
            {"key": "drive", "version": "1.1.0", "changes": ["Поддержка PDF и современных Microsoft Office форматов до 25 МБ."]},
            {"key": "primavtodor", "version": "0.4.0", "changes": ["Добавлены Табель, Гараж и Сотрудники как отдельные модули."]},
        ],
    },
    {
        "version": "00.00.26",
        "title": "Стабилизация updater и Cloud.ru",
        "summary": "Исправлены shortSha, prelaunch updater и состояние Cloud.ru без ключа.",
        "modules": [
            {"key": "updater", "version": "1.0.2", "changes": ["Исправлен экран обновления и сообщение prelaunch-обновления."]},
            {"key": "account", "version": "1.0.2", "changes": ["Cloud.ru без ключа больше не отдаёт ошибочный 422."]},
        ],
    },
    {
        "version": "00.00.25",
        "title": "Папки документов и проект Примавтодор",
        "summary": "Добавлены document_folders, work/home проекты и отдельное пространство АО «Примавтодор».",
        "modules": [
            {"key": "drive", "version": "1.0.0", "changes": ["Создание папок и загрузка файлов внутрь выбранной папки."]},
            {"key": "primavtodor", "version": "0.3.0", "changes": ["Автосоздание рабочего проекта и отдельный модуль проекта."]},
        ],
    },
    {
        "version": "00.00.24",
        "title": "Чистый чат и состояние системы",
        "summary": "Технические карточки удалены из ленты; состояние системы вынесено в отдельное окно.",
        "modules": [
            {"key": "miyori_ai", "version": "0.8.0", "changes": ["Чат очищен от Brain/RAG/Agent карточек."]},
            {"key": "settings", "version": "0.2.0", "changes": ["Состояние системы вынесено в modal."]},
        ],
    },
    {
        "version": "00.00.23",
        "title": "DeepSeek V4 Flash и упрощённая навигация",
        "summary": "DeepSeek V4 Flash стала предпочитаемой моделью; меню и чат упрощены.",
        "modules": [
            {"key": "account", "version": "0.9.0", "changes": ["DeepSeek V4 Flash выбрана как предпочтительная Cloud.ru модель."]},
            {"key": "miyori_ai", "version": "0.7.0", "changes": ["Убраны лишние элементы управления чатом."]},
        ],
    },
    {
        "version": "00.00.22",
        "title": "Cloud.ru model catalog и FastAPI lifespan",
        "summary": "Модели загружаются из Cloud.ru /models; startup hook заменён на lifespan.",
        "modules": [
            {"key": "account", "version": "0.8.0", "changes": ["Model ID выбирается из живого списка Cloud.ru."]},
            {"key": "settings", "version": "0.1.0", "changes": ["Переход на современный FastAPI lifespan."]},
        ],
    },
    {
        "version": "00.00.21",
        "title": "Standalone workspace и portable updater",
        "summary": "Служебные разделы вынесены из чата в отдельные рабочие экраны; добавлен ZIP updater для установок без .git.",
        "modules": [
            {"key": "updater", "version": "1.0.0", "changes": ["Portable ZIP обновление с резервной копией и сохранением локальных данных."]},
            {"key": "projects", "version": "0.4.0", "changes": ["Разделы открываются как отдельные workspace без чата."]},
        ],
    },
    {
        "version": "00.00.20",
        "title": "Проверка реального Cloud.ru chat/completions",
        "summary": "Тест Cloud.ru стал проверять не только ключ, но и выбранную чат-модель.",
        "modules": [
            {"key": "account", "version": "0.7.0", "changes": ["Реальный тест chat/completions и диагностика Model ID."]},
        ],
    },
    {
        "version": "00.00.19",
        "title": "Личный кабинет Cloud.ru и updater",
        "summary": "Добавлены безопасное локальное хранение Cloud.ru ключа и GitHub updater.",
        "modules": [
            {"key": "account", "version": "0.6.0", "changes": ["Сохранение ключа, модели и Base URL в локальный .env."]},
            {"key": "updater", "version": "0.8.0", "changes": ["Trusted origin, main, clean worktree и ff-only обновление."]},
        ],
    },
    {
        "version": "00.00.18",
        "title": "Главное боковое меню",
        "summary": "Добавлены пункты Мобильное приложение, Личный кабинет, Настройки и Обновление проекта.",
        "modules": [
            {"key": "projects", "version": "0.3.0", "changes": ["Сформирована базовая навигация Miyori."]},
        ],
    },
    {
        "version": "00.00.17",
        "title": "RAG Core",
        "summary": "Введён локальный hybrid RAG с FTS5, lexical retrieval, памятью и эпистемическими знаниями.",
        "modules": [
            {"key": "rag", "version": "1.0.0", "changes": ["FTS5 + lexical + RRF, контекстный бюджет и source caps."]},
        ],
    },
    {
        "version": "00.00.16",
        "title": "Epistemic Core",
        "summary": "Добавлены утверждения, источники, evidence, противоречия и правила проверки знаний.",
        "modules": [
            {"key": "epistemic", "version": "1.0.0", "changes": ["Candidate/supported/verified/disputed/rejected/superseded и evidence graph."]},
        ],
    },
    {
        "version": "00.00.15",
        "title": "Persona Pack 2.0",
        "summary": "Интегрирована каноническая личность Miyori Kitsune с биографией, фразами и диалогами.",
        "modules": [
            {"key": "persona", "version": "2.0.0", "changes": ["Persona Pack v2.0.0, биография, 700 фраз и 300 диалогов."]},
        ],
    },
]


def module_manifest() -> dict:
    return {
        "project_version": PROJECT_VERSION,
        "modules": [
            {"key": key, **value}
            for key, value in MODULES.items()
        ],
        "latest_release": RELEASES[0],
    }


def release_history() -> list[dict]:
    return RELEASES
