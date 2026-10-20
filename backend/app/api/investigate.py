"""Investigation endpoints — evidence gathering, AI reasoning, progress streaming, and history."""

import asyncio
import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from app.ai.reasoning import AIReasoningEngine
from app.core.auth import AuthenticatedUser, get_current_user, get_optional_user
from app.kubernetes.cluster_service import ClusterService
from app.models.schemas import ContextsListResponse, InvestigateRequest, InvestigationResponse
from app.services.history import HistoryService
from app.services.investigation import InvestigationService
from app.services.progress import ProgressTracker

router = APIRouter(tags=["investigation"])


@router.get("/kubernetes/contexts", response_model=ContextsListResponse)
@router.get("/contexts", response_model=ContextsListResponse)
async def list_kubernetes_contexts(
    check: bool = Query(default=True, description="Whether to probe cluster reachability"),
    _user: AuthenticatedUser | None = Depends(get_optional_user),
) -> ContextsListResponse:
    """Discover all Kubernetes contexts from kubeconfig with reachability status."""
    service = ClusterService()
    return await service.list_contexts(check_reachability=check)


@router.post("/investigate", response_model=InvestigationResponse)
async def investigate_cluster(
    request_data: InvestigateRequest | None = None,
    investigation_id: str | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
) -> InvestigationResponse:
    """Run a full cluster investigation on the selected Kubernetes cluster context.

    Requires authentication via InsForge bearer token.
    Validates cluster reachability before beginning investigation.
    """
    cluster_service = ClusterService()

    # Determine context to investigate
    selected_context: str | None = None
    if request_data and request_data.context:
        # Validate that the requested context exists and is reachable
        ctx_info = await cluster_service.validate_context(request_data.context)
        selected_context = ctx_info.name
    else:
        # Fall back to default context from kubeconfig
        contexts_resp = await cluster_service.list_contexts(check_reachability=False)
        selected_context = contexts_resp.current_context

    inv_id = investigation_id or str(uuid.uuid4())
    logger.info(
        f"POST /investigate — starting investigation [id={inv_id}] on context='{selected_context}' for user={user.email} ({user.id})"
    )

    ProgressTracker.start_investigation(inv_id)

    # Step 1: Collect Kubernetes evidence using the selected context
    service = InvestigationService(context=selected_context)
    payload = await service.run(investigation_id=inv_id)

    # Step 2: AI Reasoning (Senior SRE)
    await ProgressTracker.update_stage(inv_id, "ai_reasoning")
    logger.info(f"POST /investigate — starting AI reasoning diagnosis [id={inv_id}]")
    ai_engine = AIReasoningEngine()
    diagnosis = await ai_engine.diagnose(payload)

    # Step 3: Mark complete
    await ProgressTracker.update_stage(inv_id, "completed")

    logger.info(
        f"POST /investigate — diagnosis complete [id={inv_id}]: "
        f"root_cause='{diagnosis.root_cause}' (confidence={diagnosis.confidence}%)"
    )

    # Step 4: Persist to InsForge database asynchronously (does not break diagnosis if fails)
    history_service = HistoryService()
    await history_service.save_investigation(
        user_id=user.id,
        diagnosis=diagnosis,
        namespace="all",
        status="completed",
        cluster_context=selected_context,
    )

    return InvestigationResponse(
        status="success",
        context=selected_context,
        investigation=payload,
        diagnosis=diagnosis,
    )


@router.get("/investigate/history")
async def get_investigation_history(
    limit: int = Query(default=10, ge=1, le=50),
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[dict]:
    """Retrieve recent investigation history for the authenticated user."""
    history_service = HistoryService()
    return await history_service.get_user_history(user_id=user.id, limit=limit)


@router.get("/investigate/progress/{investigation_id}")
async def get_investigation_progress(
    investigation_id: str,
    request: Request,
) -> StreamingResponse:
    """Server-Sent Events (SSE) stream for realtime investigation progress."""

    async def event_generator() -> AsyncGenerator[str, None]:
        # Send current stages immediately
        completed = ProgressTracker.get_completed_stages(investigation_id)
        yield f"data: {json.dumps({'investigation_id': investigation_id, 'completed_stages': completed})}\n\n"

        queue = ProgressTracker.subscribe(investigation_id)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    update = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(update)}\n\n"
                    if update.get("stage") == "completed":
                        break
                except asyncio.TimeoutError:
                    # Keepalive ping
                    yield ": ping\n\n"
        finally:
            ProgressTracker.unsubscribe(investigation_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
