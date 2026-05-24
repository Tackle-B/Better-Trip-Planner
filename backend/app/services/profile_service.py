"""用户画像提取服务"""

import json
from typing import List, Dict, Any, Optional
from app.models.schemas import ChatMessage, UserProfile
from app.services.memory_service import MemoryService
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ProfileService:
    """用户画像提取和管理服务"""

    def __init__(self, memory_service: MemoryService):
        self.memory = memory_service
        logger.info("ProfileService initialized")

    async def extract_preferences_from_conversation(
        self,
        messages: List[ChatMessage],
        llm_service
    ) -> Dict[str, Any]:
        """从对话中提取用户偏好

        使用 LLM 分析对话内容，提取结构化的用户偏好
        """
        if not messages:
            return {}

        # 构建对话文本
        conversation_text = "\n".join([
            f"{'用户' if msg.role == 'user' else '助手'}: {msg.content}"
            for msg in messages
        ])

        # 提取偏好的 Prompt
        extraction_prompt = f"""请分析以下对话，提取用户的旅行偏好和特征。

对话内容：
{conversation_text}

请以 JSON 格式返回用户偏好，包含以下字段：
- budget: 预算水平（low/medium/high）
- pace: 旅行节奏（relaxed/moderate/fast）
- interests: 兴趣列表（如 ["美食", "历史", "自然"]）
- accommodation_preference: 住宿偏好（如 "经济型酒店"）
- transportation_preference: 交通偏好（如 "公共交通"）
- special_requirements: 特殊要求列表

只返回 JSON，不要其他文字："""

        try:
            # 调用 LLM 提取
            response = await llm_service.ainvoke(extraction_prompt)

            # 解析 JSON
            # 尝试提取 JSON 部分
            response = response.strip()
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()

            preferences = json.loads(response)
            logger.info(f"Extracted preferences: {preferences}")
            return preferences

        except Exception as e:
            logger.error(f"Failed to extract preferences: {e}")
            # 返回默认值
            return {
                "budget": "medium",
                "pace": "moderate",
                "interests": [],
                "accommodation_preference": "",
                "transportation_preference": "",
                "special_requirements": []
            }

    async def generate_tags_from_preferences(
        self,
        preferences: Dict[str, Any]
    ) -> List[str]:
        """从偏好生成标签"""
        tags = []

        # 预算标签
        budget = preferences.get("budget", "")
        if budget:
            tags.append(f"budget_{budget}")

        # 节奏标签
        pace = preferences.get("pace", "")
        if pace:
            tags.append(f"pace_{pace}")

        # 兴趣标签
        interests = preferences.get("interests", [])
        for interest in interests:
            tags.append(f"interest_{interest}")

        # 交通偏好标签
        transport = preferences.get("transportation_preference", "")
        if "公共交通" in transport:
            tags.append("public_transport_lover")
        elif "自驾" in transport:
            tags.append("self_drive_lover")

        return tags

    async def update_user_profile(
        self,
        user_id: str,
        new_preferences: Dict[str, Any],
        merge: bool = True
    ) -> UserProfile:
        """更新用户画像

        Args:
            user_id: 用户ID
            new_preferences: 新的偏好数据
            merge: 是否与现有偏好合并（True）还是覆盖（False）
        """
        # 获取现有画像
        existing_profile = await self.memory.retrieve_user_profile(user_id)

        if existing_profile and merge:
            # 合并偏好（新数据优先）
            merged_preferences = {**existing_profile.preferences, **new_preferences}

            # 合并标签（去重）
            new_tags = await self.generate_tags_from_preferences(new_preferences)
            merged_tags = list(set(existing_profile.tags + new_tags))

            profile = UserProfile(
                user_id=user_id,
                preferences=merged_preferences,
                tags=merged_tags,
                updated_at=datetime.now()
            )
        else:
            # 创建新画像
            tags = await self.generate_tags_from_preferences(new_preferences)
            profile = UserProfile(
                user_id=user_id,
                preferences=new_preferences,
                tags=tags
            )

        # 保存到向量库
        await self.memory.save_user_profile(user_id, profile)

        logger.info(f"Updated user profile for {user_id}")
        return profile

    async def extract_and_update_profile(
        self,
        user_id: str,
        messages: List[ChatMessage],
        llm_service
    ) -> Optional[UserProfile]:
        """从对话中提取偏好并更新用户画像

        这是一个便捷方法，组合了提取和更新操作
        """
        try:
            # 提取偏好
            preferences = await self.extract_preferences_from_conversation(
                messages,
                llm_service
            )

            if not preferences:
                return None

            # 更新画像
            profile = await self.update_user_profile(
                user_id,
                preferences,
                merge=True
            )

            return profile

        except Exception as e:
            logger.error(f"Failed to extract and update profile: {e}")
            return None

    async def get_user_profile(
        self,
        user_id: str
    ) -> Optional[UserProfile]:
        """获取用户画像"""
        return await self.memory.retrieve_user_profile(user_id)

    async def get_profile_summary(
        self,
        user_id: str
    ) -> str:
        """获取用户画像的文本摘要"""
        profile = await self.get_user_profile(user_id)

        if not profile:
            return "暂无用户画像信息"

        summary_parts = []

        # 预算
        budget = profile.preferences.get("budget", "")
        if budget:
            budget_map = {"low": "经济型", "medium": "中等", "high": "高端"}
            summary_parts.append(f"预算: {budget_map.get(budget, budget)}")

        # 节奏
        pace = profile.preferences.get("pace", "")
        if pace:
            pace_map = {"relaxed": "悠闲", "moderate": "适中", "fast": "紧凑"}
            summary_parts.append(f"节奏: {pace_map.get(pace, pace)}")

        # 兴趣
        interests = profile.preferences.get("interests", [])
        if interests:
            summary_parts.append(f"兴趣: {', '.join(interests)}")

        # 特殊要求
        special = profile.preferences.get("special_requirements", [])
        if special:
            summary_parts.append(f"特殊要求: {', '.join(special)}")

        return " | ".join(summary_parts) if summary_parts else "暂无详细偏好"


# 全局单例
_profile_service: Optional[ProfileService] = None


def get_profile_service(memory_service: MemoryService) -> ProfileService:
    """获取画像服务单例"""
    global _profile_service
    if _profile_service is None:
        _profile_service = ProfileService(memory_service)
    return _profile_service
