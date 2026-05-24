"""旅行计划管理路由"""

from fastapi import APIRouter, HTTPException, Path, Query
from typing import Optional
from ...models.schemas import (
    SaveTripPlanRequest,
    UpdateTripPlanRequest,
    SavedTripPlanResponse,
    TripPlanListResponse,
    ErrorResponse
)
from ...services.plan_service import get_plan_service
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/plans", tags=["plans"])


@router.post("", response_model=SavedTripPlanResponse)
async def save_plan(request: SaveTripPlanRequest):
    """保存旅行计划"""
    try:
        plan_service = get_plan_service()
        saved_plan = await plan_service.save_plan(
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            title=request.title,
            plan=request.plan
        )

        return SavedTripPlanResponse(
            success=True,
            message="计划保存成功",
            data=saved_plan
        )

    except Exception as e:
        logger.error(f"Save plan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{plan_id}", response_model=SavedTripPlanResponse)
async def get_plan(plan_id: str = Path(..., description="计划ID")):
    """获取旅行计划详情"""
    try:
        plan_service = get_plan_service()
        saved_plan = await plan_service.get_plan(plan_id)

        if not saved_plan:
            raise HTTPException(status_code=404, detail="计划不存在")

        return SavedTripPlanResponse(
            success=True,
            message="获取成功",
            data=saved_plan
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get plan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{plan_id}", response_model=SavedTripPlanResponse)
async def update_plan(
    plan_id: str = Path(..., description="计划ID"),
    request: UpdateTripPlanRequest = None
):
    """更新旅行计划"""
    try:
        plan_service = get_plan_service()
        saved_plan = await plan_service.update_plan(
            plan_id=plan_id,
            title=request.title,
            plan=request.plan
        )

        if not saved_plan:
            raise HTTPException(status_code=404, detail="计划不存在")

        return SavedTripPlanResponse(
            success=True,
            message="更新成功",
            data=saved_plan
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update plan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{plan_id}")
async def delete_plan(plan_id: str = Path(..., description="计划ID")):
    """删除旅行计划"""
    try:
        plan_service = get_plan_service()
        success = await plan_service.delete_plan(plan_id)

        if not success:
            raise HTTPException(status_code=404, detail="计划不存在")

        return {"success": True, "message": "删除成功"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete plan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=TripPlanListResponse)
async def list_plans(
    user_id: Optional[str] = Query(default=None, description="用户ID"),
    conversation_id: Optional[str] = Query(default=None, description="会话ID"),
    limit: int = Query(default=50, ge=1, le=100, description="返回数量")
):
    """列出旅行计划"""
    try:
        plan_service = get_plan_service()
        plans = await plan_service.list_plans(
            user_id=user_id,
            conversation_id=conversation_id,
            limit=limit
        )

        return TripPlanListResponse(
            success=True,
            data=plans
        )

    except Exception as e:
        logger.error(f"List plans error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
