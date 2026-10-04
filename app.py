from __future__ import annotations

import hashlib
import ipaddress
import platform
import socket
import threading
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from time import perf_counter
from miyori.chat_intelligence import plan_chat_query,enhance_context_route
from miyori.chat_history_recall import relevant_history,wants_history
from miyori.answer_check import check_numeric_support
from miyori.chat_feedback import (
    init_chat_feedback_db,record_chat_feedback,
    relevant_owner_corrections,feedback_totals,
)
from miyori.chat_metrics import (
    init_chat_metrics_db,store_model_usage,model_usage_summary,
)
from miyori.document_links import related_documents
from miyori.screen_context import (
    normalize_screen_context,resolve_screen_document,
)
from miyori.document_comparisons import (
    init_document_comparisons_db,
    enqueue_document_comparison,
    get_document_comparison,
)
from miyori.conversation_ui import (
    attached_document_context,
    chat_message_page,
    fork_conversation_before_message,
    init_conversation_ui_db,
    list_chat_conversations,
    set_message_bookmark,
    update_chat_conversation,
    list_bookmarked_messages,
    search_conversation_messages,
)
from miyori.config import settings
from miyori.appearance import (
    get_appearance_profile,
    init_appearance_db,
    portrait_asset_path,
    remove_portrait_asset,
    save_portrait_asset,
    update_appearance_profile,
)
from miyori.db import (
    add_message,
    conversation_messages,
    create_project,
    ensure_conversation,
    decide_permission_request,
    disconnect_device_session,
    get_account_profile,
    get_ai_preferences,
    get_agent_trace,
    get_agent_workflow,
    get_agent_workflow_by_request_key,
    get_message_by_client_request_id,
    get_permission_request,
    get_workflow_step,
    get_project,
    init_db,
    add_document,
    create_document_folder,
    find_document_by_sha,
    get_document,
    get_document_folder_parts,
    list_deleted_documents,
    list_deleted_document_folders,
    mark_document_deleted,
    mark_document_folder_deleted,
    restore_document_record,
    restore_document_folder_record,
    update_document_storage_path,
    create_employee,
    create_counterparty,
    create_contract,
    create_invoice_offer,
    create_home_device,
    create_parental_profile,
    create_task,
    delete_employee,
    delete_counterparty,
    delete_contract,
    delete_invoice_offer,
    development_snapshot,
    list_conversations,
    list_device_sessions,
    list_document_folders,
    list_documents,
    list_employees,
    list_counterparties,
    list_contracts,
    list_invoice_offers,
    list_home_devices,
    list_parental_profiles,
    list_project_modules,
    list_projects,
    list_memory_facts,
    list_agent_workflows,
    list_audit_events,
    list_permission_requests,
    list_workflow_events,
    list_workflow_steps,
    list_tasks,
    mark_interrupted_runtime_for_recovery,
    maybe_capture_user_memory,
    recent_messages,
    record_audit_event,
    record_workflow_event,
    replace_memory_fact,
    search_document_chunks,
    recent_development_checks,
    request_task_cancel,
    search_verified_memory,
    update_account_avatar,
    update_account_profile,
    update_ai_preferences,
    update_employee,
    update_counterparty,
    update_contract,
    update_invoice_offer,
    update_home_device,
    update_parental_profile,
    set_agent_run_status,
    update_agent_workflow,
    update_memory_status,
    update_workflow_step,
    upsert_device_session,
    verified_memory_context,
    find_document_folder,
)
from miyori.agent import cancel_agent_workflow, run_agent, resume_agent_workflow
from miyori.agent_workspace import (
    cancel_agent_workspace,
    create_agent_workspace,
    enqueue_agent_workspace,
    get_agent_workspace,
    init_agent_workspace_db,
    list_agent_workspaces,
)
from miyori.background import register_background_handlers
from miyori.brain import build_context
from miyori.context_router import ContextRoute, route_context
from miyori.development import run_project_self_check
from miyori.documents import (
    MAX_FILE_BYTES,
    chunk_text,
    drive_relative_root,
    extract_structured_document,
    ensure_drive_folder,
    migrate_legacy_document,
    move_document_to_trash,
    move_folder_to_trash,
    project_drive_dir,
    resolve_data_path,
    restore_document_from_trash,
    restore_folder_from_trash,
    safe_filename,
    safe_folder_name,
    save_original,
    sha256_bytes,
)
from miyori.document_intelligence import (
    build_local_document_intelligence,
    document_context_packet,
    document_intelligence_status,
    enqueue_deep_document_analysis,
    get_document_intelligence,
    get_document_nodes,
    init_document_intelligence_db,
    mark_document_intelligence_unavailable,
    rebuild_document_intelligence,
    search_document_nodes,
)
from miyori.document_questions import (
    enqueue_exhaustive_document_question,
    get_document_question,
    init_document_questions_db,
    list_document_questions,
    list_document_question_windows,
)
from miyori.provider import ProviderError, chat
from miyori.persona import persona_metadata
from miyori.epistemic import (
    add_evidence,
    capture_user_claims,
    create_claim,
    create_source,
    epistemic_snapshot,
    get_claim as get_epistemic_claim,
    init_epistemic_db,
    list_claims as list_epistemic_claims,
    trusted_claim_context,
    verify_claim,
)
from miyori.tasks import start_worker_monitor, wake_worker, worker_status
from miyori.rag import init_rag, rag_status, retrieve as rag_retrieve
from miyori.planner import MAX_AGENT_STEPS
from miyori.sources import build_answer_sources
from miyori.tools import (
    execute_approved_request,
    execute_tool,
    list_tools,
    reconcile_recoverable_operations,
)
from miyori.account import cloudru_profile, list_cloudru_models, save_cloudru_profile, test_cloudru
from miyori.module_registry import module_manifest, release_history
from miyori.nexus import build_nexus_snapshot
from miyori.nexus_actions import build_nexus_action_center
from miyori.nexus_knowledge import build_nexus_knowledge_center
from miyori.nexus_surfaces import build_nexus_surfaces
from miyori.nexus_presence import build_nexus_presence
from miyori.nexus_voice import build_nexus_voice_contract
from miyori.nexus_body import build_nexus_body
from miyori.nexus_home import (
    bind_parental_profile,
    build_nexus_home,
    init_nexus_home_db,
    link_home_device,
    record_home_heartbeat,
    unlink_home_device,
)
from miyori.proactive import apply_proactive_decision, build_nexus_proactive
from miyori.nexus_events import list_nexus_events
from miyori.system_settings import (
    cleanup_runtime_logs,
    load_system_settings,
    open_data_folder,
    save_system_settings,
    system_snapshot,
)
from miyori.updater import (
    UpdateError,
    apply_update,
    clear_restart_required,
    local_status as update_status,
    start_update_monitor,
)

ROOT = Path(__file__).resolve().parent


def _sync_project_drive(project_id: int) -> None:
    """Создаёт физическое дерево Drive и переносит ссылки со старого хранилища."""
    project_drive_dir(project_id)
    for folder in list_document_folders(project_id):
        try:
            ensure_drive_folder(
                project_id,
                get_document_folder_parts(project_id, int(folder["id"])),
            )
        except (OSError, ValueError):
            continue

    for document in list_documents(project_id):
        try:
            folder_parts = get_document_folder_parts(
                project_id,
                document.get("folder_id"),
            )
            migrated = migrate_legacy_document(
                project_id,
                document["stored_path"],
                document["filename"],
                document["sha256"],
                folder_parts,
            )
            if migrated != document["stored_path"]:
                update_document_storage_path(
                    project_id,
                    int(document["id"]),
                    migrated,
                )
        except (OSError, ValueError):
            # Исходный путь остаётся в БД; данные не удаляются при неудачной миграции.
            continue


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_conversation_ui_db()
    init_chat_metrics_db()
    init_chat_feedback_db()
    init_document_intelligence_db()
    init_document_questions_db()
    init_document_comparisons_db()
    init_agent_workspace_db()
    init_nexus_home_db()
    init_appearance_db()
    recovery_marked = mark_interrupted_runtime_for_recovery()
    recovery_checked = reconcile_recoverable_operations(allow_retry=False)
    init_epistemic_db()
    for project in list_projects():
        _sync_project_drive(int(project["id"]))
    init_rag()
    register_background_handlers()
    wake_worker()
    start_worker_monitor()
    clear_restart_required()
    start_update_monitor()
    app.state.runtime_recovery = {
        "marked": recovery_marked,
        "checked": recovery_checked,
    }
    yield


app = FastAPI(title="Miyori Kitsune AI", version="00.00.72", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.middleware("http")
async def no_cache_static_assets(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


class ComparisonRequest(BaseModel):
    question: str = Field(min_length=1,max_length=5000)
    document_ids: list[int] = Field(min_length=2,max_length=5)
    conversation_id: int | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    project_id: int
    conversation_id: int | None = None
    request_id: str | None = Field(default=None, min_length=8, max_length=128)
    attachment_ids: list[int] = Field(default_factory=list, max_length=5)
    read_only: bool = False
    ui_context: dict = Field(default_factory=dict)


class MessageFeedbackRequest(BaseModel):
    verdict: str = Field(max_length=20)
    correction: str = Field(default="",max_length=2000)


class ConversationUiPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    pinned: bool | None = None


class MessageBookmarkRequest(BaseModel):
    bookmarked: bool


class ConversationForkRequest(BaseModel):
    pass


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: str = Field(default="home", pattern="^(home|work)$")


class DocumentFolderCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    parent_id: int | None = None


class MemoryStatusRequest(BaseModel):
    status: str = Field(pattern="^(candidate|verified|disputed|superseded)$")


class MemoryReplaceRequest(BaseModel):
    statement: str = Field(min_length=1, max_length=1000)


class ToolExecuteRequest(BaseModel):
    name: str
    arguments: dict = Field(default_factory=dict)
    request_id: str | None = Field(default=None, min_length=8, max_length=128)


class TaskCreateRequest(BaseModel):
    task_type: str = Field(
        pattern="^(self_check|memory_consolidation|epistemic_review|document_intelligence|document_question)$"
    )
    payload: dict = Field(default_factory=dict)


class AgentWorkspaceNodeRequest(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    role: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    instruction: str = Field(min_length=1, max_length=6000)
    capability: str = Field(default="read_only", pattern="^(read_only|standard)$")
    depends_on: list[str] = Field(default_factory=list, max_length=8)
    step_budget: int = Field(default=3, ge=1, le=5)


class AgentWorkspaceCreateRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=6000)
    max_parallel: int = Field(default=2, ge=1, le=3)
    nodes: list[AgentWorkspaceNodeRequest] | None = Field(default=None, max_length=8)


class DocumentAnalysisRequest(BaseModel):
    force: bool = False


class DocumentQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=5000)
    force: bool = False


class PermissionDecisionRequest(BaseModel):
    approved: bool


class ClaimCreateRequest(BaseModel):
    statement: str = Field(min_length=1, max_length=1000)
    claim_type: str | None = Field(default=None, pattern="^(fact|preference|hypothesis|strategy)$")


class SourceCreateRequest(BaseModel):
    source_type: str = Field(pattern="^(user_message|document|tool|external|manual)$")
    source_key: str | None = Field(default=None, max_length=300)
    title: str | None = Field(default=None, max_length=300)
    locator: str | None = Field(default=None, max_length=1000)
    publisher: str | None = Field(default=None, max_length=300)
    quality: float = Field(default=0.5, ge=0.0, le=1.0)
    independent_group: str | None = Field(default=None, max_length=300)
    metadata: dict = Field(default_factory=dict)


class EvidenceCreateRequest(BaseModel):
    source_id: int
    stance: str = Field(pattern="^(supports|contradicts|neutral)$")
    excerpt: str | None = Field(default=None, max_length=2000)
    weight: float = Field(default=1.0, ge=0.0, le=2.0)


class SystemSettingsRequest(BaseModel):
    general: dict = {}
    automation: dict = {}


class AiPreferencesRequest(BaseModel):
    communication_style: str = Field(pattern="^(balanced|warm|business|minimal)$")
    detail_level: str = Field(pattern="^(short|normal|detailed)$")
    initiative_level: str = Field(pattern="^(low|medium|high)$")
    ask_before_assuming: bool = False
    suggest_next_steps: bool = True
    use_rag: bool = True
    use_verified_memory: bool = True
    show_uncertainty: bool = True
    priority_mode: str = Field(pattern="^(accuracy|balanced|speed)$")
    operating_mode: str = Field(pattern="^(personal|work|analyst|research|developer)$")


class HomeDeviceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    device_type: str = Field(default="device", max_length=80)
    address: str = Field(default="", max_length=180)
    status: str = Field(default="offline", max_length=40)
    notes: str = Field(default="", max_length=1000)


class NexusHomeLinkRequest(BaseModel):
    capabilities: list[str] = Field(default_factory=list, max_length=10)


class NexusHomeHeartbeatRequest(BaseModel):
    credential: str = Field(min_length=16, max_length=256)
    capabilities: list[str] | None = Field(default=None, max_length=10)
    reported_state: dict = Field(default_factory=dict)


class NexusHomeParentalBindRequest(BaseModel):
    device_id: int = Field(gt=0)


class ParentalProfileRequest(BaseModel):
    child_name: str = Field(min_length=1, max_length=160)
    device_name: str = Field(min_length=1, max_length=160)
    daily_limit_minutes: int = Field(default=120, ge=0, le=1440)
    bedtime_start: str = Field(default="21:00", max_length=10)
    bedtime_end: str = Field(default="07:00", max_length=10)
    blocked_categories: str = Field(default="", max_length=1000)
    status: str = Field(default="draft", max_length=40)


class CounterpartyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=220)
    inn: str = Field(default="", max_length=32)
    kpp: str = Field(default="", max_length=32)
    legal_address: str = Field(default="", max_length=500)
    contact_person: str = Field(default="", max_length=180)
    phone: str = Field(default="", max_length=80)
    email: str = Field(default="", max_length=180)


class ContractRequest(BaseModel):
    counterparty_id: int | None = None
    contract_number: str = Field(min_length=1, max_length=120)
    contract_date: str = Field(default="", max_length=32)
    subject: str = Field(default="", max_length=1000)
    amount: float = 0
    status: str = Field(default="draft", max_length=40)


class InvoiceOfferRequest(BaseModel):
    counterparty_id: int | None = None
    contract_id: int | None = None
    offer_number: str = Field(min_length=1, max_length=120)
    issue_date: str = Field(default="", max_length=32)
    amount: float = 0
    terms: str = Field(default="", max_length=3000)
    status: str = Field(default="draft", max_length=40)


class EmployeeRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=180)
    department: str = Field(default="", max_length=160)
    position: str = Field(default="", max_length=160)
    fuel_card_number: str = Field(default="", max_length=120)


class AccountProfileRequest(BaseModel):
    owner_name: str = Field(default="", max_length=120)
    miyori_address: str = Field(default="Господин", max_length=80)
    language: str = Field(default="ru-RU", max_length=20)
    timezone: str = Field(default="UTC", max_length=80)
    profile_kind: str = Field(default="personal", pattern="^(personal|work)$")


class MiyoriAppearanceRequest(BaseModel):
    hair_color: str | None = Field(default=None, max_length=80)
    eye_color: str | None = Field(default=None, max_length=80)
    tail_count: int | None = Field(default=None, ge=1)
    main_outfit: str | None = Field(default=None, max_length=500)


class CloudRuProfileRequest(BaseModel):
    api_key: str | None = Field(default=None, max_length=500)
    base_url: str | None = Field(default=None, max_length=500)
    model_id: str | None = Field(default=None, max_length=300)


class CloudRuTestRequest(BaseModel):
    api_key: str | None = Field(default=None, max_length=500)
    base_url: str | None = Field(default=None, max_length=500)
    model_id: str | None = Field(default=None, max_length=300)


class ProactiveDecisionRequest(BaseModel):
    signal_key: str = Field(min_length=1, max_length=240)
    fingerprint: str = Field(min_length=8, max_length=64)
    decision: str = Field(pattern="^(dismissed|snoozed)$")
    snooze_minutes: int | None = Field(default=None, ge=1, le=1440)


def _require_local_admin(request: Request) -> None:
    host = request.client.host if request.client else ""
    try:
        if ipaddress.ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise HTTPException(
        status_code=403,
        detail="Эта операция разрешена только с локального устройства.",
    )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "templates" / "index.html")


@app.get("/api/status")
def status() -> dict:
    return {
        "name": "Miyori Kitsune AI",
        "version": "00.00.72",
        "persona": persona_metadata(),
        "provider": "Cloud.ru Foundation Models",
        "provider_configured": bool(
            settings.cloudru_api_key and settings.cloudru_model_id
        ),
        "model_id": settings.cloudru_model_id or None,
        "storage": "SQLite",
        "rag": rag_status(),
    }


def _touch_current_device() -> dict:
    host = socket.gethostname() or "Local computer"
    platform_name = f"{platform.system()} {platform.release()}".strip()
    raw_key = f"{host}|{platform.machine()}|{platform.system()}"
    device_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:24]
    return upsert_device_session(
        device_key=device_key,
        device_name=host,
        platform_name=platform_name,
        session_kind="desktop",
    )


@app.get("/api/miyori/appearance")
def miyori_appearance_get(request: Request) -> dict:
    _require_local_admin(request)
    return {"appearance": get_appearance_profile()}


@app.put("/api/miyori/appearance")
def miyori_appearance_update(
    request: MiyoriAppearanceRequest,
    http_request: Request,
) -> dict:
    _require_local_admin(http_request)
    try:
        appearance = update_appearance_profile(
            hair_color=request.hair_color,
            eye_color=request.eye_color,
            tail_count=request.tail_count,
            main_outfit=request.main_outfit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"appearance": appearance}


@app.post("/api/miyori/appearance/portrait")
async def miyori_appearance_portrait_upload(
    request: Request,
    file: UploadFile = File(...),
) -> dict:
    _require_local_admin(request)
    data = await file.read()
    try:
        appearance = save_portrait_asset(data, file.content_type or "")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"appearance": appearance}


@app.delete("/api/miyori/appearance/portrait")
def miyori_appearance_portrait_delete(request: Request) -> dict:
    _require_local_admin(request)
    return {"appearance": remove_portrait_asset()}


@app.get("/api/miyori/appearance/portrait")
def miyori_appearance_portrait(request: Request) -> FileResponse:
    _require_local_admin(request)
    path = portrait_asset_path()
    if not path:
        raise HTTPException(status_code=404, detail="Портрет Миёри не задан.")
    return FileResponse(
        path,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@app.get("/api/account/profile")
def account_profile_get(request: Request) -> dict:
    _require_local_admin(request)
    current_device = _touch_current_device()
    profile = get_account_profile()
    profile["avatar_url"] = (
        "/api/account/profile/avatar"
        if profile.get("avatar_path")
        else None
    )
    return {
        "profile": profile,
        "current_device": current_device,
        "devices": list_device_sessions(),
    }


@app.put("/api/account/profile")
def account_profile_save(request: AccountProfileRequest, http_request: Request) -> dict:
    _require_local_admin(http_request)
    try:
        profile = update_account_profile(
            owner_name=request.owner_name,
            miyori_address=request.miyori_address,
            language=request.language,
            timezone_name=request.timezone,
            profile_kind=request.profile_kind,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    profile["avatar_url"] = (
        "/api/account/profile/avatar"
        if profile.get("avatar_path")
        else None
    )
    return {"profile": profile}


@app.post("/api/account/profile/avatar")
async def account_profile_avatar_upload(
    request: Request,
    file: UploadFile = File(...),
) -> dict:
    _require_local_admin(request)
    allowed = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }
    suffix = allowed.get(file.content_type or "")
    if not suffix:
        raise HTTPException(
            status_code=422,
            detail="Аватар должен быть PNG, JPEG или WEBP.",
        )
    data = await file.read()
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(
            status_code=422,
            detail="Аватар слишком большой. Максимум 2 МБ.",
        )
    profile_dir = settings.data_dir / "profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    for old in profile_dir.glob("avatar.*"):
        try:
            old.unlink()
        except OSError:
            pass
    target = profile_dir / f"avatar{suffix}"
    target.write_bytes(data)
    relative = str(target.relative_to(settings.data_dir))
    profile = update_account_avatar(relative)
    profile["avatar_url"] = "/api/account/profile/avatar"
    return {"profile": profile}


@app.get("/api/account/profile/avatar")
def account_profile_avatar(request: Request) -> FileResponse:
    _require_local_admin(request)
    profile = get_account_profile()
    avatar_path = profile.get("avatar_path")
    if not avatar_path:
        raise HTTPException(status_code=404, detail="Аватар не задан.")
    path = settings.data_dir / avatar_path
    if not path.exists():
        raise HTTPException(status_code=404, detail="Файл аватара не найден.")
    return FileResponse(path)


@app.post("/api/account/devices/{session_id}/disconnect")
def account_device_disconnect(session_id: int, request: Request) -> dict:
    _require_local_admin(request)
    if not disconnect_device_session(session_id):
        raise HTTPException(status_code=404, detail="Сессия не найдена.")
    return {"ok": True, "devices": list_device_sessions()}


@app.get("/api/account/cloudru")
def account_cloudru_get(request: Request) -> dict:
    _require_local_admin(request)
    return {"cloudru": cloudru_profile()}


@app.put("/api/account/cloudru")
async def account_cloudru_save(request: CloudRuProfileRequest, http_request: Request) -> dict:
    _require_local_admin(http_request)
    try:
        model = (request.model_id or "").strip()
        if model:
            catalog = await list_cloudru_models(
                api_key=request.api_key,
                base_url=request.base_url,
            )
            chat_ids = {item["id"] for item in catalog["chat_models"]}
            if model not in chat_ids:
                raise ValueError(
                    f"«{model}» не является доступной чат-моделью Cloud.ru. "
                    "Выберите Model ID из загруженного списка."
                )
        profile = save_cloudru_profile(
            api_key=request.api_key,
            base_url=request.base_url,
            model_id=request.model_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"cloudru": profile}


@app.get("/api/account/cloudru/models")
async def account_cloudru_models(request: Request) -> dict:
    _require_local_admin(request)
    try:
        return await list_cloudru_models()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/account/cloudru/test")
async def account_cloudru_test(request: CloudRuTestRequest, http_request: Request) -> dict:
    _require_local_admin(http_request)
    try:
        return await test_cloudru(
            api_key=request.api_key,
            base_url=request.base_url,
            model_id=request.model_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/settings")
def system_settings_get(request: Request) -> dict:
    _require_local_admin(request)
    return {
        "settings": load_system_settings(),
        "system": system_snapshot(),
        "worker": worker_status(),
        "update": update_status(fetch=False),
        "modules": module_manifest(),
    }


@app.put("/api/settings")
def system_settings_save(request: SystemSettingsRequest, http_request: Request) -> dict:
    _require_local_admin(http_request)
    try:
        saved = save_system_settings({
            "general": request.general,
            "automation": request.automation,
        })
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "settings": saved,
        "restart_required": True,
        "message": "Часть системных настроек применится после перезапуска Miyori.",
    }


@app.post("/api/settings/open-data")
def settings_open_data(request: Request) -> dict:
    _require_local_admin(request)
    try:
        open_data_folder()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True}


@app.get("/api/settings/diagnostics")
def settings_diagnostics(request: Request, project_id: int = 1) -> dict:
    _require_local_admin(request)
    checks = run_project_self_check(project_id) if get_project(project_id) else []
    update = update_status(fetch=False)
    failed_tasks = []
    if get_project(project_id):
        failed_tasks = [
            item for item in list_tasks(project_id)
            if item.get("status") == "failed"
        ][:10]
    errors = []
    if update.get("last_error"):
        errors.append("Updater: " + str(update["last_error"]))
    for item in failed_tasks:
        result = item.get("result") or {}
        message = result.get("error") if isinstance(result, dict) else str(result)
        if message:
            errors.append(f"Task #{item.get('id')}: {message}")
    return {
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "project_version": "00.00.72",
        "system": system_snapshot(),
        "worker": worker_status(),
        "update": update,
        "modules": module_manifest(),
        "self_check": [
            {"name": item.name, "passed": item.passed, "details": item.details}
            for item in checks
        ],
        "last_errors": errors[:12],
    }


@app.post("/api/settings/cleanup-runtime")
def settings_cleanup_runtime(request: Request) -> dict:
    _require_local_admin(request)
    return cleanup_runtime_logs()


@app.get("/api/modules")
def modules_manifest() -> dict:
    return module_manifest()


@app.get("/api/update/changelog")
def update_changelog(request: Request) -> dict:
    _require_local_admin(request)
    return {
        "manifest": module_manifest(),
        "releases": release_history(),
    }


@app.get("/api/ai/preferences")
def ai_preferences_get(request: Request) -> dict:
    _require_local_admin(request)
    return {"preferences": get_ai_preferences()}


@app.put("/api/ai/preferences")
def ai_preferences_save(request: AiPreferencesRequest, http_request: Request) -> dict:
    _require_local_admin(http_request)
    try:
        preferences = update_ai_preferences(
            communication_style=request.communication_style,
            detail_level=request.detail_level,
            initiative_level=request.initiative_level,
            ask_before_assuming=request.ask_before_assuming,
            suggest_next_steps=request.suggest_next_steps,
            use_rag=request.use_rag,
            use_verified_memory=request.use_verified_memory,
            show_uncertainty=request.show_uncertainty,
            priority_mode=request.priority_mode,
            operating_mode=request.operating_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"preferences": preferences}


@app.get("/api/update/status")
def project_update_status(request: Request, refresh: bool = False) -> dict:
    _require_local_admin(request)
    return {"update": update_status(fetch=refresh)}


@app.post("/api/update/check")
def project_update_check(request: Request) -> dict:
    _require_local_admin(request)
    return {"update": update_status(fetch=True)}


@app.post("/api/update/apply")
def project_update_apply(request: Request) -> dict:
    _require_local_admin(request)
    try:
        return {"update": apply_update()}
    except UpdateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/projects")
def projects() -> dict:
    return {"projects": list_projects()}


@app.post("/api/projects")
def project_create(request: ProjectCreateRequest) -> dict:
    try:
        project = create_project(request.name, kind=request.kind)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _sync_project_drive(int(project["id"]))
    return {"project": project}


@app.get("/api/projects/{project_id}/modules")
def project_modules(project_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return {"modules": list_project_modules(project_id)}


@app.get("/api/projects/{project_id}/nexus/home")
def project_nexus_home(project_id: int) -> dict:
    try:
        return build_nexus_home(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/nexus/home/devices/{device_id}/link")
def project_nexus_home_device_link(
    project_id: int,
    device_id: int,
    request: NexusHomeLinkRequest,
    http_request: Request,
) -> dict:
    _require_local_admin(http_request)
    try:
        return link_home_device(
            project_id,
            device_id,
            capabilities=request.capabilities,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/nexus/home/devices/{device_id}/unlink")
def project_nexus_home_device_unlink(
    project_id: int,
    device_id: int,
    http_request: Request,
) -> dict:
    _require_local_admin(http_request)
    try:
        return {"home": unlink_home_device(project_id, device_id)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/nexus/home/devices/{device_id}/heartbeat")
def project_nexus_home_device_heartbeat(
    project_id: int,
    device_id: int,
    request: NexusHomeHeartbeatRequest,
) -> dict:
    try:
        return {
            "home": record_home_heartbeat(
                project_id,
                device_id,
                credential=request.credential,
                capabilities=request.capabilities,
                reported_state=request.reported_state,
            )
        }
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/nexus/home/parental/{profile_id}/bind")
def project_nexus_home_parental_bind(
    project_id: int,
    profile_id: int,
    request: NexusHomeParentalBindRequest,
    http_request: Request,
) -> dict:
    _require_local_admin(http_request)
    try:
        return {
            "home": bind_parental_profile(
                project_id,
                profile_id,
                request.device_id,
            )
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/home-devices")
def home_devices_get(project_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return {"items": list_home_devices(project_id)}


@app.post("/api/projects/{project_id}/home-devices")
def home_devices_create(project_id: int, request: HomeDeviceRequest) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        item = create_home_device(project_id, **request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"item": item}


@app.put("/api/projects/{project_id}/home-devices/{item_id}")
def home_devices_update(project_id: int, item_id: int, request: HomeDeviceRequest) -> dict:
    try:
        item = update_home_device(project_id, item_id, **request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not item:
        raise HTTPException(status_code=404, detail="Устройство не найдено.")
    return {"item": item}


@app.delete("/api/projects/{project_id}/home-devices/{item_id}")
def home_devices_delete(project_id: int, item_id: int) -> dict:
    if not delete_home_device(project_id, item_id):
        raise HTTPException(status_code=404, detail="Устройство не найдено.")
    return {"ok": True}


@app.get("/api/projects/{project_id}/parental-controls")
def parental_controls_get(project_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return {"items": list_parental_profiles(project_id)}


@app.post("/api/projects/{project_id}/parental-controls")
def parental_controls_create(project_id: int, request: ParentalProfileRequest) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        item = create_parental_profile(project_id, **request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"item": item}


@app.put("/api/projects/{project_id}/parental-controls/{item_id}")
def parental_controls_update(project_id: int, item_id: int, request: ParentalProfileRequest) -> dict:
    try:
        item = update_parental_profile(project_id, item_id, **request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not item:
        raise HTTPException(status_code=404, detail="Профиль контроля не найден.")
    return {"item": item}


@app.delete("/api/projects/{project_id}/parental-controls/{item_id}")
def parental_controls_delete(project_id: int, item_id: int) -> dict:
    if not delete_parental_profile(project_id, item_id):
        raise HTTPException(status_code=404, detail="Профиль контроля не найден.")
    return {"ok": True}


@app.get("/api/projects/{project_id}/business-folders")
def project_business_folders(project_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    names = ("Контрагенты", "Договоры", "Счёт-Оферта")
    return {
        "folders": {
            name: find_document_folder(project_id, name)
            for name in names
        }
    }


@app.get("/api/projects/{project_id}/counterparties")
def counterparties_get(project_id: int) -> dict:
    if not get_project(project_id): raise HTTPException(status_code=404, detail="Проект не найден.")
    return {"items": list_counterparties(project_id)}


@app.post("/api/projects/{project_id}/counterparties")
def counterparties_create(project_id: int, request: CounterpartyRequest) -> dict:
    if not get_project(project_id): raise HTTPException(status_code=404, detail="Проект не найден.")
    try: item = create_counterparty(project_id, **request.model_dump())
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"item": item}


@app.put("/api/projects/{project_id}/counterparties/{item_id}")
def counterparties_update(project_id: int, item_id: int, request: CounterpartyRequest) -> dict:
    try: item = update_counterparty(project_id, item_id, **request.model_dump())
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not item: raise HTTPException(status_code=404, detail="Контрагент не найден.")
    return {"item": item}


@app.delete("/api/projects/{project_id}/counterparties/{item_id}")
def counterparties_delete(project_id: int, item_id: int) -> dict:
    if not delete_counterparty(project_id, item_id): raise HTTPException(status_code=404, detail="Контрагент не найден.")
    return {"ok": True}


@app.get("/api/projects/{project_id}/contracts")
def contracts_get(project_id: int) -> dict:
    return {"items": list_contracts(project_id)}


@app.post("/api/projects/{project_id}/contracts")
def contracts_create(project_id: int, request: ContractRequest) -> dict:
    try: item = create_contract(project_id, **request.model_dump())
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"item": item}


@app.put("/api/projects/{project_id}/contracts/{item_id}")
def contracts_update(project_id: int, item_id: int, request: ContractRequest) -> dict:
    try: item = update_contract(project_id, item_id, **request.model_dump())
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not item: raise HTTPException(status_code=404, detail="Договор не найден.")
    return {"item": item}


@app.delete("/api/projects/{project_id}/contracts/{item_id}")
def contracts_delete(project_id: int, item_id: int) -> dict:
    if not delete_contract(project_id, item_id): raise HTTPException(status_code=404, detail="Договор не найден.")
    return {"ok": True}


@app.get("/api/projects/{project_id}/invoice-offers")
def invoice_offers_get(project_id: int) -> dict:
    return {"items": list_invoice_offers(project_id)}


@app.post("/api/projects/{project_id}/invoice-offers")
def invoice_offers_create(project_id: int, request: InvoiceOfferRequest) -> dict:
    try: item = create_invoice_offer(project_id, **request.model_dump())
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"item": item}


@app.put("/api/projects/{project_id}/invoice-offers/{item_id}")
def invoice_offers_update(project_id: int, item_id: int, request: InvoiceOfferRequest) -> dict:
    try: item = update_invoice_offer(project_id, item_id, **request.model_dump())
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not item: raise HTTPException(status_code=404, detail="Счёт-оферта не найден.")
    return {"item": item}


@app.delete("/api/projects/{project_id}/invoice-offers/{item_id}")
def invoice_offers_delete(project_id: int, item_id: int) -> dict:
    if not delete_invoice_offer(project_id, item_id): raise HTTPException(status_code=404, detail="Счёт-оферта не найден.")
    return {"ok": True}


@app.get("/api/projects/{project_id}/employees")
def project_employees(project_id: int) -> dict:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return {"employees": list_employees(project_id)}


@app.post("/api/projects/{project_id}/employees")
def project_employee_create(project_id: int, request: EmployeeRequest) -> dict:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        employee = create_employee(
            project_id,
            full_name=request.full_name,
            department=request.department,
            position=request.position,
            fuel_card_number=request.fuel_card_number,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"employee": employee}


@app.put("/api/projects/{project_id}/employees/{employee_id}")
def project_employee_update(project_id: int, employee_id: int, request: EmployeeRequest) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        employee = update_employee(
            project_id,
            employee_id,
            full_name=request.full_name,
            department=request.department,
            position=request.position,
            fuel_card_number=request.fuel_card_number,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not employee:
        raise HTTPException(status_code=404, detail="Сотрудник не найден.")
    return {"employee": employee}


@app.delete("/api/projects/{project_id}/employees/{employee_id}")
def project_employee_delete(project_id: int, employee_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    if not delete_employee(project_id, employee_id):
        raise HTTPException(status_code=404, detail="Сотрудник не найден.")
    return {"ok": True}


@app.get("/api/projects/{project_id}/chat/metrics")
def chat_metrics(project_id: int, days: int = 30) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404,detail="Проект не найден.")
    return model_usage_summary(project_id, days=days)


@app.get("/api/projects/{project_id}/conversations")
def conversations(project_id: int, q: str = "") -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return {"conversations": list_chat_conversations(project_id, q)}


@app.patch("/api/projects/{project_id}/conversations/{conversation_id}")
def conversation_update(project_id: int, conversation_id: int, payload: ConversationUiPatch) -> dict:
    try:
        updated = update_chat_conversation(
            project_id, conversation_id, title=payload.title, pinned=payload.pinned
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"conversation": updated}


@app.get("/api/projects/{project_id}/conversations/{conversation_id}")
def conversation(
    project_id: int, conversation_id: int,
    before_id: int | None = None, limit: int = 80,
) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        page = chat_message_page(
            project_id, conversation_id, before_id=before_id, limit=limit
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "conversation_id": conversation_id,
        "project_id": project_id,
        **page,
    }


@app.get("/api/projects/{project_id}/bookmarks")
def chat_bookmarks(project_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return {"bookmarks": list_bookmarked_messages(project_id)}


@app.post("/api/projects/{project_id}/conversations/{conversation_id}/messages/{message_id}/feedback")
def conversation_feedback_create(
    project_id: int, conversation_id: int,message_id: int,
    request: MessageFeedbackRequest,
) -> dict:
    try:
        saved=record_chat_feedback(
            project_id,conversation_id,message_id,
            request.verdict,request.correction,
        )
        return {"feedback":saved}
    except LookupError as exc:
        raise HTTPException(status_code=404,detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/chat/feedback-summary")
def conversation_feedback_summary(project_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404,detail="Проект не найден.")
    return feedback_totals(project_id)


@app.get("/api/projects/{project_id}/conversations/{conversation_id}/search")
def conversation_search(project_id: int, conversation_id: int, q: str = "") -> dict:
    try:
        return {
            "matches": search_conversation_messages(project_id, conversation_id, q)
        }
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/api/projects/{project_id}/conversations/{conversation_id}/messages/{message_id}/bookmark")
def message_bookmark(
    project_id: int, conversation_id: int, message_id: int,
    payload: MessageBookmarkRequest,
) -> dict:
    try:
        return set_message_bookmark(
            project_id, conversation_id, message_id, payload.bookmarked
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/conversations/{conversation_id}/messages/{message_id}/fork")
def message_fork(project_id: int, conversation_id: int, message_id: int) -> dict:
    try:
        return fork_conversation_before_message(project_id, conversation_id, message_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/memory")
def memory(project_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return {"facts": list_memory_facts(project_id)}


@app.patch("/api/projects/{project_id}/memory/{fact_id}")
def memory_status(project_id: int, fact_id: int, request: MemoryStatusRequest) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        fact = update_memory_status(project_id, fact_id, request.status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not fact:
        raise HTTPException(status_code=404, detail="Факт не найден.")
    return {"fact": fact}


@app.get("/api/projects/{project_id}/memory/search")
def memory_search(project_id: int, q: str = "") -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return {"facts": search_verified_memory(project_id, q, limit=12)}


@app.post("/api/projects/{project_id}/memory/{fact_id}/replace")
def memory_replace(project_id: int, fact_id: int, request: MemoryReplaceRequest) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        fact = replace_memory_fact(project_id, fact_id, request.statement)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"fact": fact}


@app.get("/api/projects/{project_id}/documents")
def documents(project_id: int, folder_id: int | None = None) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    _sync_project_drive(project_id)
    trashed_documents = list_deleted_documents(project_id)
    trashed_folders = list_deleted_document_folders(project_id)
    return {
        "documents": list_documents(project_id, folder_id=folder_id),
        "folders": list_document_folders(project_id),
        "storage_root": drive_relative_root(project_id),
        "trash_count": len(trashed_documents) + len(trashed_folders),
    }


@app.get("/api/projects/{project_id}/document-folders")
def document_folders(project_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return {"folders": list_document_folders(project_id)}


@app.post("/api/projects/{project_id}/document-folders")
def document_folder_create(project_id: int, request: DocumentFolderCreateRequest) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        clean_name = safe_folder_name(request.name)
        parent_parts = get_document_folder_parts(project_id, request.parent_id)
        folder = create_document_folder(
            project_id,
            clean_name,
            parent_id=request.parent_id,
        )
        ensure_drive_folder(project_id, [*parent_parts, clean_name])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Не удалось создать папку на диске: {exc}") from exc
    return {"folder": folder}


@app.delete("/api/projects/{project_id}/document-folders/{folder_id}")
def document_folder_delete(project_id: int, folder_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        parts = get_document_folder_parts(project_id, folder_id)
        trash_path = move_folder_to_trash(project_id, parts, folder_id)
        folder = mark_document_folder_deleted(project_id, folder_id, trash_path)
        if not folder:
            raise ValueError("Папка не найдена.")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Не удалось переместить папку в корзину: {exc}") from exc
    init_rag()
    return {
        "ok": True,
        "folder": folder,
        "message": "Папка перемещена в корзину. Оригиналы сохранены на диске.",
    }


@app.post("/api/projects/{project_id}/document-folders/{folder_id}/restore")
def document_folder_restore(project_id: int, folder_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    folder = next(
        (item for item in list_deleted_document_folders(project_id) if int(item["id"]) == folder_id),
        None,
    )
    if not folder:
        raise HTTPException(status_code=404, detail="Папка не найдена в корзине.")

    try:
        parent_parts: list[str] = []
        parent_id = folder.get("parent_id")
        if parent_id is not None:
            try:
                parent_parts = get_document_folder_parts(project_id, int(parent_id))
            except ValueError as exc:
                raise ValueError(
                    "Сначала восстановите родительскую папку."
                ) from exc
        _, restored_name = restore_folder_from_trash(
            project_id,
            folder["trash_path"],
            parent_parts,
            folder["name"],
        )
        restored = restore_document_folder_record(
            project_id,
            folder_id,
            restored_name=restored_name,
        )
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    init_rag()
    return {"ok": True, "folder": restored}


@app.post("/api/projects/{project_id}/documents")
async def document_upload(
    project_id: int,
    file: UploadFile = File(...),
    folder_id: int | None = Form(default=None),
) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")

    filename = safe_filename(file.filename or "document.txt")
    data = await file.read()

    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status_code=422, detail="Файл слишком большой. Текущий лимит — 25 МБ.")

    try:
        folder_parts = get_document_folder_parts(project_id, folder_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    chunks: list[str] = []
    structured = None
    index_warning: str | None = None
    try:
        structured = extract_structured_document(filename, data)
        chunks = chunk_text(structured.text)
        if not chunks:
            index_warning = "В файле нет извлекаемого текста для базы знаний."
    except ValueError as exc:
        # Оригинал сохраняется даже если формат/OCR пока не позволяет построить знания.
        index_warning = str(exc)

    digest = sha256_bytes(data)
    existing = find_document_by_sha(project_id, digest, include_deleted=True)
    if existing and not existing.get("deleted_at"):
        intelligence = get_document_intelligence(project_id, int(existing["id"]))
        if not intelligence and structured is not None:
            intelligence = build_local_document_intelligence(
                project_id,
                int(existing["id"]),
                structured,
            )
        return {
            "document": existing,
            "chunk_count": existing.get("chunk_count", len(chunks)),
            "duplicate": True,
            "intelligence": intelligence,
            "message": "Этот оригинал уже хранится в проекте.",
        }

    try:
        stored_path = save_original(
            project_id,
            filename,
            data,
            digest,
            folder_parts,
        )
        document = add_document(
            project_id=project_id,
            filename=filename,
            stored_path=stored_path,
            mime_type=file.content_type,
            sha256=digest,
            size_bytes=len(data),
            chunks=chunks,
            folder_id=folder_id,
        )
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        if structured is not None:
            intelligence = build_local_document_intelligence(
                project_id,
                int(document["id"]),
                structured,
            )
        else:
            lower_warning = (index_warning or "").lower()
            intelligence = mark_document_intelligence_unavailable(
                project_id,
                int(document["id"]),
                status="needs_ocr" if "ocr" in lower_warning else "unsupported",
                error=index_warning or "Текст документа не извлечён.",
            )
    except Exception as exc:
        intelligence = mark_document_intelligence_unavailable(
            project_id,
            int(document["id"]),
            status="failed",
            error=f"Не удалось построить локальную структуру: {exc}",
        )

    init_rag()
    return {
        "document": document,
        "chunk_count": len(chunks),
        "duplicate": False,
        "indexed": bool(chunks),
        "intelligence": intelligence,
        "index_warning": index_warning,
        "message": (
            "Оригинал сохранён в Miyori Drive и добавлен в базу знаний."
            if chunks else
            "Оригинал сохранён в Miyori Drive. Файл пока не проиндексирован."
        ),
    }


@app.get("/api/projects/{project_id}/documents/trash")
def document_trash(project_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return {
        "documents": list_deleted_documents(project_id),
        "folders": list_deleted_document_folders(project_id),
        "storage_root": drive_relative_root(project_id),
    }


@app.get("/api/projects/{project_id}/documents/intelligence/status")
def document_intelligence_project_status(project_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return document_intelligence_status(project_id)


@app.get("/api/projects/{project_id}/documents/{document_id}/related")
def document_related(project_id: int, document_id: int, limit: int = 8) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        return related_documents(project_id,document_id,limit=limit)
    except LookupError as exc:
        raise HTTPException(status_code=404,detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/documents/{document_id}/intelligence")
def document_intelligence_get(project_id: int, document_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    if not get_document(project_id, document_id):
        raise HTTPException(status_code=404, detail="Документ не найден.")
    profile = get_document_intelligence(project_id, document_id)
    if not profile:
        try:
            profile = rebuild_document_intelligence(project_id, document_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"intelligence": profile}


@app.get("/api/projects/{project_id}/documents/{document_id}/outline")
def document_outline(project_id: int, document_id: int) -> dict:
    profile = get_document_intelligence(project_id, document_id)
    if not profile:
        try:
            profile = rebuild_document_intelligence(project_id, document_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "document_id": document_id,
        "title": profile.get("title"),
        "status": profile.get("status"),
        "coverage_ratio": profile.get("coverage_ratio"),
        "outline": profile.get("outline") or [],
    }


@app.get("/api/projects/{project_id}/documents/{document_id}/nodes")
def document_nodes(
    project_id: int,
    document_id: int,
    offset: int = 0,
    limit: int = 200,
) -> dict:
    if not get_document(project_id, document_id):
        raise HTTPException(status_code=404, detail="Документ не найден.")
    return {
        "nodes": get_document_nodes(
            project_id,
            document_id,
            offset=max(0, offset),
            limit=max(1, min(limit, 1000)),
        )
    }


@app.get("/api/projects/{project_id}/documents/{document_id}/deep-search")
def document_deep_search(
    project_id: int,
    document_id: int,
    q: str = "",
    limit: int = 12,
) -> dict:
    if not get_document(project_id, document_id):
        raise HTTPException(status_code=404, detail="Документ не найден.")
    query = q.strip()
    if not query:
        return {"nodes": []}
    return {
        "nodes": search_document_nodes(
            project_id,
            document_id,
            query,
            limit=max(1, min(limit, 40)),
            neighbor_radius=1,
        ),
        "context": document_context_packet(
            project_id,
            document_id,
            query,
            max_chars=14_000,
        ),
    }


@app.post("/api/projects/{project_id}/documents/{document_id}/intelligence/rebuild")
def document_intelligence_rebuild(project_id: int, document_id: int) -> dict:
    if not get_document(project_id, document_id):
        raise HTTPException(status_code=404, detail="Документ не найден.")
    try:
        profile = rebuild_document_intelligence(project_id, document_id)
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    init_rag()
    return {"intelligence": profile}


@app.post("/api/projects/{project_id}/documents/{document_id}/intelligence/analyze")
def document_intelligence_analyze(
    project_id: int,
    document_id: int,
    request: DocumentAnalysisRequest,
) -> dict:
    if not get_document(project_id, document_id):
        raise HTTPException(status_code=404, detail="Документ не найден.")
    try:
        task = enqueue_deep_document_analysis(
            project_id,
            document_id,
            force=request.force,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    wake_worker()
    return {
        "task": task,
        "intelligence": get_document_intelligence(project_id, document_id),
    }


@app.post("/api/projects/{project_id}/document-comparisons")
def document_comparison_create(project_id: int, request: ComparisonRequest) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404,detail="Проект не найден.")
    try:
        comparison=enqueue_document_comparison(
            project_id,request.document_ids,request.question,
            conversation_id=request.conversation_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
    wake_worker()
    return {"comparison":comparison}


@app.get("/api/projects/{project_id}/document-comparisons/{comparison_id}")
def document_comparison_get(project_id: int, comparison_id: int) -> dict:
    try:
        return {"comparison":get_document_comparison(project_id,comparison_id)}
    except LookupError as exc:
        raise HTTPException(status_code=404,detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/documents/{document_id}/questions")
def document_questions_list(
    project_id: int,
    document_id: int,
    limit: int = 30,
) -> dict:
    if not get_document(project_id, document_id):
        raise HTTPException(status_code=404, detail="Документ не найден.")
    return {
        "questions": list_document_questions(
            project_id,
            document_id,
            limit=max(1, min(limit, 100)),
        )
    }


@app.post("/api/projects/{project_id}/documents/{document_id}/questions")
def document_question_create(
    project_id: int,
    document_id: int,
    request: DocumentQuestionRequest,
) -> dict:
    if not get_document(project_id, document_id):
        raise HTTPException(status_code=404, detail="Документ не найден.")
    try:
        question = enqueue_exhaustive_document_question(
            project_id,
            document_id,
            request.question,
            force=request.force,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    wake_worker()
    return {"question": question}


@app.get("/api/projects/{project_id}/documents/{document_id}/questions/{question_id}")
def document_question_get(
    project_id: int,
    document_id: int,
    question_id: int,
    include_windows: bool = False,
) -> dict:
    question = get_document_question(
        project_id,
        document_id,
        question_id,
    )
    if not question:
        raise HTTPException(status_code=404, detail="Полный вопрос по документу не найден.")
    response = {"question": question}
    if include_windows:
        response["windows"] = list_document_question_windows(
            project_id,
            document_id,
            question_id,
        )
    return response


@app.get("/api/projects/{project_id}/documents/{document_id}/download")
def document_download(project_id: int, document_id: int) -> FileResponse:
    document = get_document(project_id, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Документ не найден.")
    try:
        path = resolve_data_path(document["stored_path"])
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Оригинал документа отсутствует на диске.")
    return FileResponse(
        path,
        media_type=document.get("mime_type") or "application/octet-stream",
        filename=document["filename"],
    )


@app.delete("/api/projects/{project_id}/documents/{document_id}")
def document_delete(project_id: int, document_id: int) -> dict:
    document = get_document(project_id, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Документ не найден.")
    try:
        trash_path = move_document_to_trash(
            project_id,
            document["stored_path"],
            document["filename"],
            document_id,
        )
        deleted = mark_document_deleted(project_id, document_id, trash_path)
        if not deleted:
            raise ValueError("Документ уже был удалён.")
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    init_rag()
    return {
        "ok": True,
        "document": deleted,
        "message": "Документ перемещён в корзину. Оригинал сохранён.",
    }


@app.post("/api/projects/{project_id}/documents/{document_id}/restore")
def document_restore(project_id: int, document_id: int) -> dict:
    document = get_document(project_id, document_id, include_deleted=True)
    if not document or not document.get("deleted_at") or not document.get("trash_path"):
        raise HTTPException(status_code=404, detail="Документ не найден в корзине.")

    folder_id = document.get("folder_id")
    try:
        folder_parts = get_document_folder_parts(project_id, folder_id)
    except ValueError:
        folder_id = None
        folder_parts = []

    try:
        stored_path = restore_document_from_trash(
            project_id,
            document["trash_path"],
            document["filename"],
            folder_parts,
        )
        restored = restore_document_record(
            project_id,
            document_id,
            stored_path,
            folder_id,
        )
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    init_rag()
    return {"ok": True, "document": restored}


@app.get("/api/projects/{project_id}/documents/search")
def document_search(project_id: int, q: str = "") -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    query = q.strip()
    if not query:
        return {"chunks": []}
    return {"chunks": search_document_chunks(project_id, query, limit=20)}


@app.get("/api/projects/{project_id}/rag")
def rag_search(project_id: int, q: str = "", limit: int = 8) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    if not q.strip():
        raise HTTPException(status_code=422, detail="Пустой RAG-запрос.")
    result = rag_retrieve(
        project_id,
        q,
        limit=max(1, min(limit, 20)),
    )
    return result.to_dict()


@app.get("/api/projects/{project_id}/nexus")
def project_nexus(project_id: int) -> dict:
    try:
        return build_nexus_snapshot(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/nexus/actions")
def project_nexus_actions(project_id: int, limit: int = 60) -> dict:
    try:
        return build_nexus_action_center(project_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/nexus/knowledge")
def project_nexus_knowledge(
    project_id: int,
    q: str = "",
    limit: int = 80,
) -> dict:
    try:
        return build_nexus_knowledge_center(
            project_id,
            query=q,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/nexus/surfaces")
def project_nexus_surfaces(
    project_id: int,
    context: str = "auto",
    q: str = "",
    limit: int = 3,
) -> dict:
    try:
        return build_nexus_surfaces(
            project_id,
            context=context,
            query=q,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/nexus/presence")
def project_nexus_presence(project_id: int) -> dict:
    try:
        return build_nexus_presence(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/nexus/voice")
def project_nexus_voice(project_id: int) -> dict:
    try:
        return build_nexus_voice_contract(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/nexus/body")
def project_nexus_body(project_id: int) -> dict:
    try:
        return build_nexus_body(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/nexus/proactive")
def project_nexus_proactive(project_id: int) -> dict:
    try:
        return build_nexus_proactive(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/nexus/proactive/decision")
def project_nexus_proactive_decision(
    project_id: int,
    request: ProactiveDecisionRequest,
) -> dict:
    try:
        return apply_proactive_decision(
            project_id,
            signal_key=request.signal_key,
            fingerprint=request.fingerprint,
            decision=request.decision,
            snooze_minutes=request.snooze_minutes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/nexus/events")
def project_nexus_events(
    project_id: int,
    after: str | None = None,
    limit: int = 100,
    tail: bool = False,
) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        return list_nexus_events(
            project_id,
            after=after,
            limit=limit,
            tail=tail,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/epistemic")
def epistemic_overview(project_id: int, status: str | None = None) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        claims = list_epistemic_claims(project_id, status=status, limit=100)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "snapshot": epistemic_snapshot(project_id),
        "claims": claims,
    }


@app.post("/api/projects/{project_id}/epistemic/claims")
def epistemic_claim_create(project_id: int, request: ClaimCreateRequest) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        claim = create_claim(
            project_id,
            request.statement,
            claim_type=request.claim_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"claim": claim}


@app.get("/api/projects/{project_id}/epistemic/claims/{claim_id}")
def epistemic_claim_get(project_id: int, claim_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    claim = get_epistemic_claim(project_id, claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Утверждение не найдено.")
    return {"claim": claim}


@app.post("/api/projects/{project_id}/epistemic/sources")
def epistemic_source_create(project_id: int, request: SourceCreateRequest) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        source = create_source(
            project_id,
            request.source_type,
            source_key=request.source_key,
            title=request.title,
            locator=request.locator,
            publisher=request.publisher,
            quality=request.quality,
            independent_group=request.independent_group,
            metadata=request.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"source": source}


@app.post("/api/projects/{project_id}/epistemic/claims/{claim_id}/evidence")
def epistemic_evidence_create(
    project_id: int,
    claim_id: int,
    request: EvidenceCreateRequest,
) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        evidence = add_evidence(
            project_id,
            claim_id,
            request.source_id,
            request.stance,
            excerpt=request.excerpt,
            weight=request.weight,
        )
        verification = verify_claim(project_id, claim_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "evidence": evidence,
        "verification": verification.__dict__,
        "claim": get_epistemic_claim(project_id, claim_id),
    }


@app.post("/api/projects/{project_id}/epistemic/claims/{claim_id}/verify")
def epistemic_claim_verify(project_id: int, claim_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        result = verify_claim(project_id, claim_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "verification": result.__dict__,
        "claim": get_epistemic_claim(project_id, claim_id),
    }



def _route_from_payload(payload: dict) -> ContextRoute:
    return ContextRoute(
        use_recent_messages=bool(payload.get("use_recent_messages", True)),
        use_user_memory=bool(payload.get("use_user_memory", False)),
        use_project_memory=bool(payload.get("use_project_memory", False)),
        use_documents=bool(payload.get("use_documents", False)),
        use_epistemic=bool(payload.get("use_epistemic", False)),
        use_tools=bool(payload.get("use_tools", False)),
        max_rag_items=int(payload.get("max_rag_items", 8)),
        reasons=tuple(payload.get("reasons") or ()),
    )


async def _build_agent_response(
    *,
    project_id: int,
    conversation_id: int,
    text: str,
    route: ContextRoute,
    agent,
    captured_memory: dict | None = None,
    captured_claims: list[dict] | None = None,
    request_id: str | None = None,
    attachment_ids: list[int] | None = None,
    user_message_id: int | None = None,
    ui_context: dict | None = None,
) -> dict:
    workflow_state = get_agent_workflow(agent.workflow_id, project_id) or {}
    current_step = int(workflow_state.get("current_step") or 0)
    response_key = (
        f"assistant:workflow:{agent.workflow_id}:"
        f"step:{current_step}:status:{agent.workflow_status}"
    )
    cached = ((workflow_state.get("result") or {}).get("last_response"))
    if cached and cached.get("response_key") == response_key:
        return cached

    context = recent_messages(conversation_id)
    query_plan = plan_chat_query(
        text,context,attached_count=len(attachment_ids or [])
    )
    query_for_sources = query_plan.retrieval_query
    started_retrieval = perf_counter()
    tool_catalog = list_tools()
    brain = build_context(
        project_id,
        text,
        route,
        tools_allowed=[item["name"] for item in tool_catalog],
    )

    ai_preferences = get_ai_preferences()
    use_rag = bool(ai_preferences.get("use_rag", 1))
    use_verified_memory = bool(ai_preferences.get("use_verified_memory", 1))

    include_documents = bool(route.use_documents and use_rag)
    include_memory = bool(
        (route.use_user_memory or route.use_project_memory)
        and use_verified_memory
    )
    include_knowledge = bool(route.use_epistemic)

    rag = rag_retrieve(
        project_id,
        query_for_sources,
        limit=route.max_rag_items,
        include_documents=include_documents,
        include_memory=include_memory,
        include_knowledge=include_knowledge,
        include_user_memory=route.use_user_memory,
        include_project_memory=route.use_project_memory,
    )
    rag_payload = rag.to_dict()

    epistemic = (
        trusted_claim_context(project_id, query_for_sources, limit=8)
        if route.use_epistemic
        else []
    )
    sources = build_answer_sources(
        project_id,
        rag_payload,
        agent.tool_context,
    )
    attachment_context, attachment_sources = attached_document_context(
        project_id, attachment_ids or []
    )
    screen_fragments,screen_sources=resolve_screen_document(
        project_id,text,ui_context or {},
    )
    attachment_context.extend(screen_fragments)
    attachment_sources.extend(screen_sources)
    retrieval_ms = round((perf_counter() - started_retrieval) * 1000)
    history_matches = relevant_history(
        project_id,text,active_conversation_id=conversation_id
    )
    if wants_history(text):
        for prior in history_matches:
            sources.append({
                "source_type":"chat_history",
                "title":"Ранее: "+prior["title"],
                "conversation_id":prior["conversation_id"],
                "message_id":prior["message_id"],
                "unverified":True,
            })
    source_ids = {s.get("document_id") for s in sources}
    for attachment in attachment_sources:
        if attachment["document_id"] not in source_ids:
            sources.append(attachment)
            source_ids.add(attachment["document_id"])

    user_corrections=relevant_owner_corrections(project_id,text)
    for correction in user_corrections:
        sources.append({
            "source_type":"owner_feedback",
            "title":"Уточнение владельца (непроверено)",
            "conversation_id":correction["conversation_id"],
            "message_id":correction["message_id"],
            "unverified":True,
        })

    actual_usage: dict = {}
    answer = await chat(
        context,
        memory_context=None,
        document_context=attachment_context or None,
        history_context=(history_matches or [{"status":"not_found"}])
                        if wants_history(text) else None,
        feedback_context=user_corrections or None,
        screen_context=ui_context or None,
        brain_plan=brain.plan,
        tool_context=agent.tool_context,
        epistemic_context=epistemic,
        rag_context=rag_payload,
        answer_sources=sources,
        usage_sink=actual_usage,
        quality_guidance=query_plan.public_summary(),
    )

    numeric_check = check_numeric_support(
        answer,
        rag_items=rag_payload.get("items",[]),
        document_fragments=attachment_context,
        verified_claims=epistemic,
    )
    unreadable_files = [
        source.get("title") for source in attachment_sources
        if source.get("readable") is False
    ]
    truncated_files = [
        source.get("title") for source in attachment_sources
        if source.get("truncated") is True
    ]
    if unreadable_files:
        evidence_status = "missing_extraction"
    elif truncated_files:
        evidence_status = "partial_extraction"
    elif not sources and (route.use_documents or route.use_epistemic):
        evidence_status = "insufficient_sources"
    elif sources:
        evidence_status = "sources_available_not_fact_checked"
    else:
        evidence_status = "not_required"
    diagnostics = {
        "plan":query_plan.public_summary(),
        "evidence":{
            "status":evidence_status,
            "source_count":len(sources),
            "unreadable":unreadable_files,
            "truncated":truncated_files,
            "semantic_fact_verification":False,
        },
        "model_usage":actual_usage,
        "retrieval_ms":retrieval_ms,
        "numeric_check":numeric_check,
        "owner_feedback_count":len(user_corrections),
        "screen_context":{
            "module":(ui_context or {}).get("module",""),
            "document_used":bool(screen_sources),
        },
        "historical_chat":{
            "requested":wants_history(text),
            "matches":len(history_matches),
            "verified_facts":False,
        },
    }

    assistant_message_id = add_message(
        conversation_id,
        "assistant",
        answer,
        metadata={
            "sources": sources,
            "context_route": route.to_dict(),
            "agent_run_id": agent.run_id,
            "workflow_id": agent.workflow_id,
            "workflow_status": agent.workflow_status,
            "request_id": request_id,
            "response_key": response_key,
            "diagnostics": diagnostics,
            "comparison_offer": (
                {"document_ids": list(attachment_ids), "question": text}
                if attachment_ids and len(attachment_ids) >= 2 else None
            ),
            "task_goal": text,
        },
        client_request_id=response_key,
    )

    store_model_usage(project_id,assistant_message_id,actual_usage)
    unique_tool_steps = {
        int(action["step_index"])
        for action in agent.actions
        if action.get("tool_name")
        and action.get("status") not in {"skipped"}
    }
    response = {
        "conversation_id": conversation_id,
        "project_id": project_id,
        "user_message_id": user_message_id,
        "assistant_message_id": assistant_message_id,
        "request_id": request_id,
        "response_key": response_key,
        "answer": answer,
        "sources": sources,
        "diagnostics": diagnostics,
        "comparison_offer": (
            {"document_ids": list(attachment_ids), "question": text}
            if attachment_ids and len(attachment_ids) >= 2 else None
        ),
        "task_goal": text,
        "attachments": attachment_sources,
        "workflow": {
            "id": agent.workflow_id,
            "status": agent.workflow_status,
            "recovery_required": agent.recovery_required,
        },
        "brain": {
            "plan": brain.plan,
            "context_route": brain.context_route,
            "working_memory": brain.working_memory,
            "tools_allowed": brain.tools_allowed,
        },
        "rag": rag_payload,
        "memory": {
            "captured": captured_memory,
            "user_scope_enabled": bool(route.use_user_memory and use_verified_memory),
            "project_scope_enabled": bool(route.use_project_memory and use_verified_memory),
        },
        "epistemic": {
            "used_claims": [
                {
                    "id": item.get("id"),
                    "statement": item.get("statement"),
                    "status": item.get("status"),
                    "assessment": item.get("assessment"),
                    "confidence": item.get("confidence"),
                    "claim_type": item.get("claim_type"),
                }
                for item in epistemic
            ],
            "captured_claim_ids": [
                item.get("id") for item in (captured_claims or [])
            ],
            "snapshot": epistemic_snapshot(project_id),
        },
        "agent": {
            "run_id": agent.run_id,
            "workflow_id": agent.workflow_id,
            "workflow_status": agent.workflow_status,
            "actions": agent.actions,
            "steps_used": len(unique_tool_steps),
            "max_steps": MAX_AGENT_STEPS,
            "planner_mode": agent.planner_mode,
            "pending_permissions": agent.pending_permissions,
            "recovery_required": agent.recovery_required,
        },
    }
    update_agent_workflow(
        agent.workflow_id,
        result={"last_response": response},
    )
    return response


@app.get("/api/tools")
def tools_catalog() -> dict:
    return {"tools": list_tools()}


@app.post("/api/projects/{project_id}/tools/execute")
def tool_execute(project_id: int, request: ToolExecuteRequest) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    try:
        return execute_tool(
            request.name,
            project_id,
            request.arguments,
            idempotency_key=(
                f"manual:{request.request_id}"
                if request.request_id else None
            ),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/permissions")
def permissions_list(project_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return {"requests": list_permission_requests(project_id)}


@app.post("/api/projects/{project_id}/permissions/{request_id}/decision")
async def permission_decision(
    project_id: int,
    request_id: int,
    request: PermissionDecisionRequest,
) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")

    original = get_permission_request(project_id, request_id)
    if not original:
        raise HTTPException(status_code=404, detail="Запрос разрешения не найден.")

    decided = decide_permission_request(project_id, request_id, request.approved)
    if not decided:
        current = get_permission_request(project_id, request_id)
        if current and (
            (request.approved and current["status"] in {"approved", "executed", "failed"})
            or (not request.approved and current["status"] == "denied")
        ):
            decided = current
        else:
            raise HTTPException(status_code=409, detail="Запрос уже обработан или не найден.")

    workflow_id = decided.get("workflow_id")
    workflow = (
        get_agent_workflow(int(workflow_id), project_id)
        if workflow_id else None
    )
    conversation_id = (
        int(workflow["conversation_id"])
        if workflow and workflow.get("conversation_id") is not None
        else None
    )

    if original["status"] == "pending":
        record_audit_event(
            project_id,
            "user",
            "permission.approved" if request.approved else "permission.denied",
            "Пользователь разрешил действие Miyori."
            if request.approved else
            "Пользователь отклонил действие Miyori.",
            conversation_id=conversation_id,
            workflow_id=int(workflow_id) if workflow_id else None,
            entity_type="permission",
            entity_id=request_id,
            details={
                "tool": decided["tool_name"],
                "preview": decided.get("preview") or {},
            },
        )

    execution = None
    execution_error = None
    if request.approved and decided["status"] != "executed":
        try:
            execution = execute_approved_request(
                project_id,
                request_id,
                conversation_id=conversation_id,
            )
        except Exception as exc:
            execution_error = str(exc)

    current_request = get_permission_request(project_id, request_id)

    continuation = None
    agent_payload = None
    if workflow_id:
        try:
            agent = await resume_agent_workflow(
                project_id,
                int(workflow_id),
                permission_request_id=request_id,
            )
            agent_payload = {
                "workflow_id": agent.workflow_id,
                "workflow_status": agent.workflow_status,
                "pending_permissions": agent.pending_permissions,
                "recovery_required": agent.recovery_required,
            }
            refreshed_workflow = get_agent_workflow(int(workflow_id), project_id)
            route = _route_from_payload((refreshed_workflow or workflow)["route"])
            try:
                continuation = await _build_agent_response(
                    project_id=project_id,
                    conversation_id=int((refreshed_workflow or workflow)["conversation_id"]),
                    text=str((refreshed_workflow or workflow)["goal"]),
                    route=route,
                    agent=agent,
                    captured_memory=None,
                    captured_claims=[],
                    request_id=None,
                )
            except ProviderError as exc:
                # The authorized action has already been resolved. Never turn a
                # post-action LLM failure into an ambiguous HTTP retry.
                execution_error = (
                    (execution_error + " | ") if execution_error else ""
                ) + f"Не удалось сформировать продолжение ответа: {exc}"
        except (ValueError, RuntimeError) as exc:
            execution_error = (
                (execution_error + " | ") if execution_error else ""
            ) + str(exc)

    if not workflow_id and request.approved and execution_error:
        raise HTTPException(status_code=422, detail=execution_error)

    return {
        "request": current_request or decided,
        "execution": execution,
        "execution_error": execution_error,
        "workflow": agent_payload,
        "continuation": continuation,
    }


@app.get("/api/projects/{project_id}/agent-workspaces")
def agent_workspaces_list(project_id: int, limit: int = 30) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return {"workspaces": list_agent_workspaces(project_id, limit=limit)}


@app.post("/api/projects/{project_id}/agent-workspaces")
def agent_workspace_create(
    project_id: int,
    request: AgentWorkspaceCreateRequest,
) -> dict:
    try:
        workspace = create_agent_workspace(
            project_id,
            request.goal,
            [item.model_dump() for item in request.nodes] if request.nodes else None,
            max_parallel=request.max_parallel,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"workspace": workspace}


@app.get("/api/projects/{project_id}/agent-workspaces/{workspace_id}")
def agent_workspace_get(project_id: int, workspace_id: int) -> dict:
    workspace = get_agent_workspace(project_id, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Agent Workspace не найден.")
    return {"workspace": workspace}


@app.post("/api/projects/{project_id}/agent-workspaces/{workspace_id}/run")
def agent_workspace_run(project_id: int, workspace_id: int) -> dict:
    try:
        task = enqueue_agent_workspace(project_id, workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    wake_worker()
    return {
        "task": task,
        "workspace": get_agent_workspace(project_id, workspace_id),
    }


@app.post("/api/projects/{project_id}/agent-workspaces/{workspace_id}/cancel")
def agent_workspace_cancel(project_id: int, workspace_id: int) -> dict:
    try:
        workspace = cancel_agent_workspace(project_id, workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"workspace": workspace}


@app.get("/api/projects/{project_id}/workflows")
def workflows_list(project_id: int, status: str | None = None) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    statuses = (status,) if status else None
    try:
        workflows = list_agent_workflows(project_id, statuses=statuses, limit=100)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"workflows": workflows}


@app.get("/api/projects/{project_id}/workflows/{workflow_id}")
def workflow_get(project_id: int, workflow_id: int) -> dict:
    workflow = get_agent_workflow(workflow_id, project_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow не найден.")
    return {
        "workflow": workflow,
        "steps": list_workflow_steps(workflow_id),
        "events": list_workflow_events(workflow_id),
        "audit": list_audit_events(project_id, workflow_id=workflow_id, limit=200),
    }


@app.post("/api/projects/{project_id}/workflows/{workflow_id}/cancel")
async def workflow_cancel(project_id: int, workflow_id: int) -> dict:
    try:
        workflow = await cancel_agent_workflow(project_id, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"workflow": workflow}


@app.post("/api/projects/{project_id}/workflows/{workflow_id}/resume")
async def workflow_resume(project_id: int, workflow_id: int) -> dict:
    workflow = get_agent_workflow(workflow_id, project_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow не найден.")
    try:
        agent = await resume_agent_workflow(
            project_id,
            workflow_id,
            recover=True,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    continuation = None
    route = _route_from_payload(workflow["route"])
    try:
        continuation = await _build_agent_response(
            project_id=project_id,
            conversation_id=int(workflow["conversation_id"]),
            text=str(workflow["goal"]),
            route=route,
            agent=agent,
            captured_memory=None,
            captured_claims=[],
            request_id=None,
        )
    except ProviderError as exc:
        return {
            "workflow": get_agent_workflow(workflow_id, project_id),
            "agent": {
                "workflow_status": agent.workflow_status,
                "recovery_required": agent.recovery_required,
            },
            "continuation": None,
            "continuation_error": str(exc),
        }
    return {
        "workflow": get_agent_workflow(workflow_id, project_id),
        "agent": {
            "workflow_status": agent.workflow_status,
            "recovery_required": agent.recovery_required,
            "pending_permissions": agent.pending_permissions,
        },
        "continuation": continuation,
    }


@app.get("/api/projects/{project_id}/audit")
def audit_list(project_id: int, workflow_id: int | None = None, limit: int = 100) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return {
        "events": list_audit_events(
            project_id,
            workflow_id=workflow_id,
            limit=limit,
        )
    }


@app.post("/api/projects/{project_id}/recovery/check")
def recovery_check(project_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return reconcile_recoverable_operations(project_id, allow_retry=False)


@app.get("/api/projects/{project_id}/tasks")
def tasks_list(project_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return {"tasks": list_tasks(project_id)}


@app.post("/api/projects/{project_id}/tasks")
def task_create(project_id: int, request: TaskCreateRequest) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    task = create_task(project_id, request.task_type, request.payload)
    wake_worker()
    return {"task": task}


@app.post("/api/projects/{project_id}/tasks/{task_id}/cancel")
def task_cancel(project_id: int, task_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    changed = request_task_cancel(project_id, task_id)
    if not changed:
        raise HTTPException(status_code=409, detail="Задачу уже нельзя отменить.")
    return {"cancel_requested": True}


@app.get("/api/projects/{project_id}/development")
def development(project_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    return {
        "snapshot": development_snapshot(project_id),
        "checks": recent_development_checks(project_id),
    }


@app.post("/api/projects/{project_id}/development/check")
def development_check(project_id: int) -> dict:
    if not get_project(project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")
    checks = run_project_self_check(project_id)
    return {
        "checks": [
            {"name": c.name, "passed": c.passed, "details": c.details}
            for c in checks
        ],
        "snapshot": development_snapshot(project_id),
    }


@app.get("/api/agent-runs/{run_id}")
def agent_trace(run_id: int) -> dict:
    trace = get_agent_trace(run_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Agent run не найден.")
    return {"run": trace}


@app.post("/api/chat")
async def send_message(request: ChatRequest) -> dict:
    text = request.message.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Сообщение пустое.")
    if not get_project(request.project_id):
        raise HTTPException(status_code=404, detail="Проект не найден.")

    # UI hints are never permissions. Document ownership must be checked
    # even when no document content is loaded.
    try:
        ui_context=normalize_screen_context(request.project_id,request.ui_context)
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc

    # Validated before the agent starts, with strict project ownership.
    attachment_ids = request.attachment_ids or []
    try:
        attached_document_context(request.project_id, attachment_ids)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    existing_message = (
        get_message_by_client_request_id(request.project_id, request.request_id)
        if request.request_id else None
    )

    if existing_message:
        if (
            existing_message["content"] != text
            or (existing_message.get("metadata") or {}).get("attachments", []) != attachment_ids
            or bool((existing_message.get("metadata") or {}).get("read_only", False)) != request.read_only
            or (existing_message.get("metadata") or {}).get("ui_context", {}) != ui_context
        ):
            raise HTTPException(
                status_code=409,
                detail="Этот request_id уже использован для другого сообщения.",
            )
        if (
            request.conversation_id is not None
            and int(existing_message["conversation_id"]) != int(request.conversation_id)
        ):
            raise HTTPException(
                status_code=409,
                detail="request_id принадлежит другому разговору.",
            )
        conversation_id = int(existing_message["conversation_id"])
        user_message_id = int(existing_message["id"])
        is_new_message = False
        request_key = f"chat:{request.request_id}"
        existing_workflow = get_agent_workflow_by_request_key(
            request.project_id,
            request_key,
        )
        cached_response = (
            ((existing_workflow or {}).get("result") or {}).get("last_response")
        )
        if cached_response:
            return cached_response
    else:
        try:
            conversation_id = ensure_conversation(
                request.conversation_id,
                request.project_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        user_message_id = add_message(
            conversation_id,
            "user",
            text,
            client_request_id=request.request_id,
            metadata={
                "attachments":attachment_ids,
                "read_only":request.read_only,
                "ui_context":ui_context,
            },
        )
        is_new_message = True
        request_key = (
            f"chat:{request.request_id}"
            if request.request_id
            else f"chat:message:{user_message_id}"
        )
        existing_workflow = None

    if is_new_message:
        record_audit_event(
            request.project_id,
            "user",
            "chat.requested",
            "Пользователь отправил запрос Miyori.",
            conversation_id=conversation_id,
            entity_type="message",
            entity_id=user_message_id,
            details={
                "request_id": request.request_id,
                "message_preview": text[:500],
                "attachment_count": len(attachment_ids),
            },
        )
        captured_memory = (
            None if request.read_only else maybe_capture_user_memory(
                request.project_id, conversation_id, user_message_id, text
            )
        )
        captured_claims = (
            [] if request.read_only else capture_user_claims(
                request.project_id, conversation_id, user_message_id, text
            )
        )
    else:
        captured_memory = None
        captured_claims = []

    message_history = recent_messages(conversation_id)
    query_plan = plan_chat_query(
        text,message_history,attached_count=len(attachment_ids)
    )
    route = (
        _route_from_payload(existing_workflow["route"])
        if existing_workflow else
        enhance_context_route(text,query_plan,forced_read_only=request.read_only)
    )
    from dataclasses import replace as replace_route
    if request.read_only:
        route = replace_route(
            route,
            use_tools=False,
            reasons=route.reasons + ("safe_read_only_fork",),
        )
    if attachment_ids and not route.use_documents:
        route = replace_route(route, use_documents=True)
    context = recent_messages(conversation_id)

    agent = await run_agent(
        request.project_id,
        conversation_id,
        text,
        route,
        conversation_context=context[-8:],
        request_key=request_key,
    )

    try:
        return await _build_agent_response(
            project_id=request.project_id,
            conversation_id=conversation_id,
            text=text,
            route=route,
            agent=agent,
            captured_memory=captured_memory,
            captured_claims=captured_claims,
            request_id=request.request_id,
            attachment_ids=attachment_ids,
            user_message_id=user_message_id,
            ui_context=ui_context,
        )
    except ProviderError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "message": str(exc),
                "conversation_id": conversation_id,
                "workflow_id": agent.workflow_id,
                "workflow_status": agent.workflow_status,
                "pending_permissions": agent.pending_permissions,
            },
        ) from exc

