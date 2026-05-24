"""记忆服务 - 混合记忆管理（Redis + Chroma）"""

import json
import redis
import chromadb
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from app.models.schemas import ChatMessage, UserProfile, Conversation
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


class MemoryService:
    """混合记忆管理服务

    - 短期记忆：Redis 存储会话对话历史（高速读写）
    - 长期记忆：Chroma 存储用户画像和历史计划（向量检索）
    """

    def __init__(self):
        # Redis 客户端（短期记忆）
        try:
            self.redis_client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password,
                decode_responses=True,
                socket_connect_timeout=5
            )
            # 测试连接
            self.redis_client.ping()
            self.redis_available = True
            logger.info("Redis connected successfully")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Running without Redis (memory will not persist).")
            self.redis_client = None
            self.redis_available = False

        # Chroma 客户端（长期记忆）
        chroma_persist_dir = settings.chroma_persist_dir
        self.chroma_client = chromadb.PersistentClient(path=chroma_persist_dir)

        # 用户画像集合
        self.profile_collection = self.chroma_client.get_or_create_collection(
            name="user_profiles",
            metadata={"description": "用户画像和偏好"}
        )

        # 历史计划集合
        self.plan_collection = self.chroma_client.get_or_create_collection(
            name="trip_plans",
            metadata={"description": "历史旅行计划"}
        )

        logger.info("MemoryService initialized successfully")

    # ============ 短期记忆（Redis）============

    async def save_conversation_history(
        self,
        conv_id: str,
        messages: List[ChatMessage]
    ) -> bool:
        """保存会话历史到 Redis"""
        if not self.redis_available:
            logger.debug("Redis not available, skipping save")
            return False

        try:
            key = f"session:{conv_id}:messages"
            # 序列化消息列表
            messages_data = [msg.model_dump(mode='json') for msg in messages]
            self.redis_client.set(key, json.dumps(messages_data, ensure_ascii=False))
            # 设置过期时间（7天）
            self.redis_client.expire(key, 7 * 24 * 3600)
            return True
        except Exception as e:
            logger.error(f"Failed to save conversation history: {e}")
            return False

    async def get_conversation_history(
        self,
        conv_id: str
    ) -> List[ChatMessage]:
        """从 Redis 获取会话历史"""
        if not self.redis_available:
            logger.debug("Redis not available, returning empty history")
            return []

        try:
            key = f"session:{conv_id}:messages"
            data = self.redis_client.get(key)
            if not data:
                return []

            messages_data = json.loads(data)
            return [ChatMessage(**msg) for msg in messages_data]
        except Exception as e:
            logger.error(f"Failed to get conversation history: {e}")
            return []

    async def append_message(
        self,
        conv_id: str,
        message: ChatMessage
    ) -> bool:
        """追加单条消息到会话历史"""
        if not self.redis_available:
            logger.debug("Redis not available, skipping append")
            return False

        try:
            messages = await self.get_conversation_history(conv_id)
            messages.append(message)
            return await self.save_conversation_history(conv_id, messages)
        except Exception as e:
            logger.error(f"Failed to append message: {e}")
            return False

    async def save_conversation_summary(
        self,
        conv_id: str,
        summary: str
    ) -> bool:
        """保存会话摘要"""
        if not self.redis_available:
            logger.debug("Redis not available, skipping summary save")
            return False

        try:
            key = f"session:{conv_id}:summary"
            self.redis_client.set(key, summary)
            self.redis_client.expire(key, 7 * 24 * 3600)
            return True
        except Exception as e:
            logger.error(f"Failed to save summary: {e}")
            return False

    async def get_conversation_summary(
        self,
        conv_id: str
    ) -> Optional[str]:
        """获取会话摘要"""
        if not self.redis_available:
            logger.debug("Redis not available, returning None")
            return None

        try:
            key = f"session:{conv_id}:summary"
            return self.redis_client.get(key)
        except Exception as e:
            logger.error(f"Failed to get summary: {e}")
            return None

    # ============ 长期记忆（Chroma）============

    async def save_user_profile(
        self,
        user_id: str,
        profile: UserProfile
    ) -> bool:
        """保存用户画像到向量库"""
        try:
            # 构建文档内容（用于向量化）
            doc_content = f"用户偏好: {json.dumps(profile.preferences, ensure_ascii=False)}\n"
            doc_content += f"用户标签: {', '.join(profile.tags)}"

            # 存储到 Chroma
            self.profile_collection.upsert(
                ids=[user_id],
                documents=[doc_content],
                metadatas=[{
                    "user_id": user_id,
                    "preferences": json.dumps(profile.preferences, ensure_ascii=False),
                    "tags": json.dumps(profile.tags, ensure_ascii=False),
                    "updated_at": profile.updated_at.isoformat()
                }]
            )
            logger.info(f"User profile saved for user_id: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save user profile: {e}")
            return False

    async def retrieve_user_profile(
        self,
        user_id: str
    ) -> Optional[UserProfile]:
        """从向量库检索用户画像"""
        try:
            results = self.profile_collection.get(ids=[user_id])
            if not results['ids']:
                return None

            metadata = results['metadatas'][0]
            return UserProfile(
                user_id=user_id,
                preferences=json.loads(metadata['preferences']),
                tags=json.loads(metadata['tags']),
                updated_at=datetime.fromisoformat(metadata['updated_at'])
            )
        except Exception as e:
            logger.error(f"Failed to retrieve user profile: {e}")
            return None

    async def search_similar_profiles(
        self,
        query: str,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """搜索相似用户画像"""
        try:
            results = self.profile_collection.query(
                query_texts=[query],
                n_results=limit
            )

            profiles = []
            if results['ids']:
                for i, doc_id in enumerate(results['ids'][0]):
                    metadata = results['metadatas'][0][i]
                    profiles.append({
                        "user_id": doc_id,
                        "preferences": json.loads(metadata['preferences']),
                        "tags": json.loads(metadata['tags']),
                        "distance": results['distances'][0][i] if 'distances' in results else None
                    })
            return profiles
        except Exception as e:
            logger.error(f"Failed to search similar profiles: {e}")
            return []

    async def save_trip_plan(
        self,
        plan_id: str,
        user_id: str,
        plan_content: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """保存历史旅行计划到向量库"""
        try:
            self.plan_collection.upsert(
                ids=[plan_id],
                documents=[plan_content],
                metadatas=[{
                    "plan_id": plan_id,
                    "user_id": user_id,
                    "created_at": datetime.now().isoformat(),
                    **metadata
                }]
            )
            logger.info(f"Trip plan saved: {plan_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save trip plan: {e}")
            return False

    async def search_similar_plans(
        self,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """搜索相似的历史计划"""
        try:
            where_filter = {"user_id": user_id} if user_id else None

            results = self.plan_collection.query(
                query_texts=[query],
                n_results=limit,
                where=where_filter
            )

            plans = []
            if results['ids']:
                for i, doc_id in enumerate(results['ids'][0]):
                    plans.append({
                        "plan_id": doc_id,
                        "content": results['documents'][0][i],
                        "metadata": results['metadatas'][0][i],
                        "distance": results['distances'][0][i] if 'distances' in results else None
                    })
            return plans
        except Exception as e:
            logger.error(f"Failed to search similar plans: {e}")
            return []

    # ============ 混合策略：构建 Agent 上下文 ============

    async def build_context_for_agent(
        self,
        conv_id: str,
        user_id: str,
        current_query: str,
        window_size: int = 10
    ) -> str:
        """构建 Agent 上下文

        策略：
        1. 滑动窗口：最近 N 轮对话
        2. 摘要：如果历史超过阈值，加载摘要
        3. 用户画像：从向量库检索
        4. 相似计划：检索历史成功案例
        """
        context_parts = []

        # 1. 从向量数据库获取用户画像
        profile = await self.retrieve_user_profile(user_id)
        if profile:
            context_parts.append("【用户画像】")
            context_parts.append(f"偏好: {json.dumps(profile.preferences, ensure_ascii=False)}")
            context_parts.append(f"标签: {', '.join(profile.tags)}")
            context_parts.append("")

        # 2. 从redis获取会话历史（滑动窗口）
        messages = await self.get_conversation_history(conv_id)
        if messages:
            # 只保留最近 window_size 轮对话
            recent_messages = messages[-window_size * 2:] if len(messages) > window_size * 2 else messages

            context_parts.append("【对话历史】")
            for msg in recent_messages:
                role_name = "用户" if msg.role == "user" else "助手"
                context_parts.append(f"{role_name}: {msg.content}")
            context_parts.append("")

            # 如果历史很长，从redis加载摘要
            if len(messages) > window_size * 2:
                summary = await self.get_conversation_summary(conv_id)
                if summary:
                    context_parts.insert(0, f"【早期对话摘要】\n{summary}\n")

        # 3. 从向量数据库检索相似的历史计划
        similar_plans = await self.search_similar_plans(current_query, user_id, limit=2)
        if similar_plans:
            context_parts.append("【相关历史计划】")
            for i, plan in enumerate(similar_plans, 1):
                context_parts.append(f"{i}. {plan['content'][:200]}...")
            context_parts.append("")

        return "\n".join(context_parts)

    # ============ 工具方法 ============

    async def clear_conversation(self, conv_id: str) -> bool:
        """清除会话数据"""
        if not self.redis_available:
            logger.debug("Redis not available, skipping clear")
            return False

        try:
            self.redis_client.delete(f"session:{conv_id}:messages")
            self.redis_client.delete(f"session:{conv_id}:summary")
            return True
        except Exception as e:
            logger.error(f"Failed to clear conversation: {e}")
            return False

    def health_check(self) -> Dict[str, bool]:
        """健康检查"""
        redis_ok = False
        chroma_ok = False

        if self.redis_available:
            try:
                self.redis_client.ping()
                redis_ok = True
            except Exception as e:
                logger.error(f"Redis health check failed: {e}")
        else:
            logger.debug("Redis not available")

        try:
            self.chroma_client.heartbeat()
            chroma_ok = True
        except Exception as e:
            logger.error(f"Chroma health check failed: {e}")

        return {
            "redis": redis_ok,
            "chroma": chroma_ok
        }


# 全局单例
_memory_service: Optional[MemoryService] = None


def get_memory_service() -> MemoryService:
    """获取记忆服务单例"""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service
