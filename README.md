# Miyori Kitsune AI

Локальный персональный AI-проект с FastAPI backend, SQLite-хранилищем, Cloud.ru LLM, Persona Pack, RAG, Epistemic Core, проектными пространствами и модульным веб-интерфейсом.

**Внутренняя версия приложения: 00.00.37.**  
Репозиторий: `Aspksa/MIYORI_KITSUNE_AI_SPEC_v1.1.0`.

## Состояние релиза 00.00.37

`00.00.37` — **Miyori AI Core v2**. Основной AI-контур переработан под дальнейшее развитие проекта:

- Context Router решает, нужны ли текущему запросу документы, пользовательская память, память проекта, Epistemic Core и инструменты;
- Agent Core использует model-assisted Planner с жёстким JSON-контрактом и deterministic fallback;
- Planner работает пошагово, видит компактный контекст последних сообщений и может выполнять до 5 проверяемых шагов;
- read-инструменты выполняются автоматически, write-инструменты по-прежнему проходят через permission layer;
- Miyori умеет читать каталог Drive и конкретные документы, создавать папки и перемещать документы только после подтверждения;
- источники документов формируются приложением, передаются модели как разрешённый source manifest и сохраняются вместе с ответом;
- память разделена на `user` и `project`, а текущий разговор остаётся working memory;
- обычные фразы не записываются автоматически в долговременную память;
- Epistemic Core показывает оценки «Подтверждено», «Вероятно», «Есть противоречия», «Недостаточно данных»;
- RAG может включать и исключать отдельные каналы retrieval в зависимости от запроса;
- добавлены тесты маршрутизации, Planner fallback, памяти, источников, межпроектной изоляции и permission safety.

## Что уже реализовано

### Miyori AI

- чат с Cloud.ru Foundation Models;
- Persona Pack `2.0.0`;
- локальный контекст проекта;
- Brain plan;
- Context Router для выборочной загрузки контекста;
- Agent Core v2 с model-assisted Planner и deterministic fallback;
- до 5 пошаговых инструментальных действий;
- компактный conversational context для ссылок «этот файл / перемести его»;
- инструменты чтения и контролируемые действия;
- разрешения на write-действия;
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

Miyori Drive сохраняет любые рабочие файлы размером до 25 MB как оригиналы. TXT, Markdown, JSON, PDF с текстовым слоем, DOCX, XLSX и PPTX дополнительно разбираются и индексируются для поиска и RAG. Неподдерживаемый формат или сканированный PDF всё равно сохраняется в Drive, но получает 0 фрагментов знаний до появления подходящего обработчика/OCR.

Каждый проект получает отдельное физическое хранилище:

```text
data/
  workspace/
    <project_id>/
      Документы - Облако - Miyori/
        Файлы/
        Корзина/
```

> В интерфейсе раздел называется «Документы / Облако / Miyori». В имени физической папки используются дефисы, потому что символ `/` является разделителем пути и не может быть частью имени папки Windows.

Папки, создаваемые через браузер, зеркалируются внутри `Файлы/`. Загруженные документы сохраняются как оригинальные байты и индексируются для Miyori. При удалении файл или целая папка перемещается в `Корзина/`; автоматического безвозвратного удаления в текущем релизе нет. Восстановление выполняется из интерфейса Drive.

Удалённые документы исключаются из RAG и поиска по активной базе знаний.

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
- `miyori/planner.py` — Planner schema, fallback и безопасная валидация решений;
- `miyori/agent.py` — пошаговый Agent Core;
- `miyori/sources.py` — манифест источников ответа;
- `miyori/tools.py` — registry и политика инструментов;
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

## Локальные данные и безопасность

- SQLite и проектные файлы хранятся локально;
- Cloud.ru API key не возвращается клиенту в открытом виде;
- write-инструменты требуют разрешения;
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

Автоматический контур покрывает Account / Cloud.ru secret handling, Persona Pack, RAG, Epistemic Core, updater safety, Miyori Drive, Context Router, Planner fallback, слои памяти, source manifest, межпроектную изоляцию чтения документов и permission safety write-инструментов.

Следующий слой покрытия: Home Network, Parental Control, Primavtodor CRUD, Settings API и полноценный mocked-provider интеграционный `/api/chat`.

## Текущие ограничения

- Planner уже model-assisted, но при недоступности Cloud.ru намеренно переключается на ограниченный deterministic fallback;
- write-планы с зависимыми шагами останавливаются на permission request и продолжаются только после подтверждения отдельного действия;
- мобильный iOS/Android клиент ещё не реализован;
- детский контроль пока не применяет политики на реальном устройстве;
- домашняя сеть пока не выполняет автоматическое обнаружение;
- OCR для сканированных PDF отсутствует;
- автоматический внешний web research не является частью текущего backend-контура.

## Версии

- `00.00.34` — домашние модули + полный UI audit + удаление processing UI;
- `00.00.35` — документация + frontend modularization + удаление processing legacy;
- `00.00.36` — физический Miyori Drive проекта + оригиналы + безопасная корзина + восстановление + поиск по содержимому;
- `00.00.37` — Miyori AI Core v2: Context Router + Planner + Agent loop + layered memory + sources + epistemic assessments + tool safety tests.

Канонический changelog приложения доступен через `miyori/module_registry.py` и API manifest/changelog.
