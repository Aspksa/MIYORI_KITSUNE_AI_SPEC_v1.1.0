from __future__ import annotations

PROJECT_VERSION = "00.00.31"

MODULES = {
    "miyori_ai": {
        "name": "Miyori Kitsune AI",
        "version": "1.1.0",
        "status": "active",
        "description": "Центр настроек личности, поведения, режима работы, памяти и автономности Miyori.",
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
    "settings": {
        "name": "Настройки",
        "version": "0.3.0",
        "status": "active",
        "description": "Системные параметры Miyori и состояние локальных компонентов.",
    },
    "drive": {
        "name": "Документы / Облако / Miyori",
        "version": "1.3.0",
        "status": "active",
        "description": "Miyori Drive: папки, поиск, drag-and-drop, Office/PDF, RAG и файловое пространство проектов.",
    },
    "projects": {
        "name": "Проекты",
        "version": "0.8.0",
        "status": "active",
        "description": "Рабочие и домашние пространства с отдельными проектными модулями.",
    },
    "primavtodor": {
        "name": "АО «Примавтодор»",
        "version": "0.5.0",
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
    "rag": {
        "name": "RAG Core",
        "version": "1.0.0",
        "status": "active",
        "description": "Hybrid FTS5 + lexical retrieval, память и проверенные знания.",
    },
    "epistemic": {
        "name": "Epistemic Core",
        "version": "1.0.0",
        "status": "active",
        "description": "Утверждения, источники, evidence, противоречия и верификация знаний.",
    },
    "persona": {
        "name": "Persona Pack",
        "version": "2.0.0",
        "status": "active",
        "description": "Каноническая личность Miyori Kitsune и правила поведения.",
    },
    "updater": {
        "name": "Обновление проекта",
        "version": "1.2.0",
        "status": "active",
        "description": "Git fast-forward и Portable ZIP updater с резервными копиями и проверкой GitHub.",
    },
}

RELEASES = [
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
