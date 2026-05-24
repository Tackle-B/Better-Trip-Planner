"""旅行计划持久化服务"""

import json
import logging
from typing import List, Optional
from datetime import datetime
from app.models.schemas import SavedTripPlan, TripPlan
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class PlanService:
    """旅行计划持久化服务

    使用文件系统存储计划（简单实现）
    生产环境可替换为数据库
    """

    def __init__(self):
        import os
        self.storage_dir = "./data/plans"
        os.makedirs(self.storage_dir, exist_ok=True)
        logger.info("PlanService initialized")

    def _get_plan_path(self, plan_id: str) -> str:
        """获取计划文件路径"""
        return f"{self.storage_dir}/{plan_id}.json"

    async def save_plan(
        self,
        user_id: str,
        conversation_id: Optional[str],
        title: str,
        plan: TripPlan
    ) -> SavedTripPlan:
        """保存旅行计划"""
        try:
            saved_plan = SavedTripPlan(
                user_id=user_id,
                conversation_id=conversation_id,
                title=title,
                plan=plan
            )

            # 保存到文件
            plan_path = self._get_plan_path(saved_plan.plan_id)
            with open(plan_path, 'w', encoding='utf-8') as f:
                json.dump(saved_plan.model_dump(mode='json'), f, ensure_ascii=False, indent=2)

            logger.info(f"Plan saved: {saved_plan.plan_id}")
            return saved_plan

        except Exception as e:
            logger.error(f"Failed to save plan: {e}")
            raise

    async def get_plan(self, plan_id: str) -> Optional[SavedTripPlan]:
        """获取旅行计划"""
        try:
            plan_path = self._get_plan_path(plan_id)

            import os
            if not os.path.exists(plan_path):
                return None

            with open(plan_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return SavedTripPlan(**data)

        except Exception as e:
            logger.error(f"Failed to get plan {plan_id}: {e}")
            return None

    async def update_plan(
        self,
        plan_id: str,
        title: Optional[str] = None,
        plan: Optional[TripPlan] = None
    ) -> Optional[SavedTripPlan]:
        """更新旅行计划"""
        try:
            saved_plan = await self.get_plan(plan_id)
            if not saved_plan:
                return None

            # 更新字段
            if title:
                saved_plan.title = title
            if plan:
                saved_plan.plan = plan
            saved_plan.updated_at = datetime.now()

            # 保存到文件
            plan_path = self._get_plan_path(plan_id)
            with open(plan_path, 'w', encoding='utf-8') as f:
                json.dump(saved_plan.model_dump(mode='json'), f, ensure_ascii=False, indent=2)

            logger.info(f"Plan updated: {plan_id}")
            return saved_plan

        except Exception as e:
            logger.error(f"Failed to update plan {plan_id}: {e}")
            raise

    async def delete_plan(self, plan_id: str) -> bool:
        """删除旅行计划"""
        try:
            plan_path = self._get_plan_path(plan_id)

            import os
            if not os.path.exists(plan_path):
                return False

            os.remove(plan_path)
            logger.info(f"Plan deleted: {plan_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete plan {plan_id}: {e}")
            return False

    async def list_plans(
        self,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        limit: int = 50
    ) -> List[SavedTripPlan]:
        """列出旅行计划"""
        try:
            import os
            plans = []

            for filename in os.listdir(self.storage_dir):
                if not filename.endswith('.json'):
                    continue

                plan_path = os.path.join(self.storage_dir, filename)
                with open(plan_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    plan = SavedTripPlan(**data)

                    # 过滤
                    if user_id and plan.user_id != user_id:
                        continue
                    if conversation_id and plan.conversation_id != conversation_id:
                        continue

                    plans.append(plan)

            # 按创建时间倒序
            plans.sort(key=lambda p: p.created_at, reverse=True)
            return plans[:limit]

        except Exception as e:
            logger.error(f"Failed to list plans: {e}")
            return []


# 全局单例
_plan_service: Optional[PlanService] = None


def get_plan_service() -> PlanService:
    """获取计划服务单例"""
    global _plan_service
    if _plan_service is None:
        _plan_service = PlanService()
    return _plan_service
