# Miyori Kitsune AI

Локальный персональный AI-проект с FastAPI backend, SQLite-хранилищем, Cloud.ru LLM, Persona Pack, RAG, Epistemic Core, проектными пространствами и модульным веб-интерфейсом.

**Внутренняя версия приложения: 00.00.35.**  
Репозиторий: `Aspksa/MIYORI_KITSUNE_AI_SPEC_v1.1.0`.

## Состояние релиза 00.00.35

`00.00.35` — архитектурный cleanup-релиз без новой пользовательской функции. Он фиксирует и упрощает функциональную базу `00.00.34`:

- синхронизирована документация с фактическим состоянием проекта;
- frontend разделён на упорядоченные JS/CSS-модули;
- полностью удалён оставшийся legacy-код визуализации внутренних этапов обработки;
- сохранены домашнее пространство, «Домашняя сеть», фундамент «Детского контроля Miyori» и UI-аудит `00.00.34`;
- версия backend, UI assets и module registry синхронизирована на `00.00.35`.

## Что уже реализовано

### Miyori AI

- чат с Cloud.ru Foundation Models;
- Persona Pack `2.0.0`;
- локальный контекст проекта;
- Brain plan;
- Agent Core с ограниченным числом шагов;
- инструменты чтения и контролируемые действия;
- разрешения на write-действия;
- фоновые задачи и self-check;
- системный статус и диагностика.

### Память и знания

- SQLite-память проекта;
- статусы фактов и ручная работа с памятью;
- Epistemic Core: claims, sources, evidence, contradictions;
- статусы `candidate / supported / verified / disputed / rejected / superseded`;
- RAG по документам, проверенной памяти и подтверждённым знаниям;
- FTS5 при наличии и lexical fallback;
- RRF-объединение каналов поиска.

### Документы / Miyori Drive

Поддерживаются TXT, Markdown, JSON, PDF с текстовым слоем, DOCX, XLSX и PPTX. Документы сохраняются локально, индексируются и могут использоваться в RAG. Максимальный размер загружаемого файла — 25 MB.

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
- `miyori/brain.py` — рабочий контекст и план;
- `miyori/agent.py` — Agent Core;
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

Текущие автоматические тесты покрывают Account / Cloud.ru secret handling, Epistemic Core, Persona Pack, RAG и updater safety.

Следующий слой покрытия: Home Network, Parental Control, Primavtodor CRUD, Settings API, permissions и интеграционный `/api/chat`.

## Текущие ограничения

- Agent Core пока использует детерминированную/эвристическую маршрутизацию, а не полноценный LLM tool planner;
- мобильный iOS/Android клиент ещё не реализован;
- детский контроль пока не применяет политики на реальном устройстве;
- домашняя сеть пока не выполняет автоматическое обнаружение;
- OCR для сканированных PDF отсутствует;
- автоматический внешний web research не является частью текущего backend-контура.

## Версии

- `00.00.34` — домашние модули + полный UI audit + удаление processing UI;
- `00.00.35` — документация + frontend modularization + удаление processing legacy.

Канонический changelog приложения доступен через `miyori/module_registry.py` и API manifest/changelog.
