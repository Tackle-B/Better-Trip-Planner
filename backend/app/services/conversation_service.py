"""会话管理服务"""

import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from ..models.schemas import Conversation, ChatMessage, ConversationCreateRequest
from ..services.memory_service import MemoryService
import logging

logger = logging.getLogger(__name__)


class ConversationService:
    """会话管理服务

    负责会话的 CRUD 操作和消息管理
    """

    def __init__(self, memory_service: MemoryService):
        self.memory = memory_service
        # 简单内存存储（生产环境可替换为 SQLite/PostgreSQL）
        self.conversations: Dict[str, Conversation] = {}
        logger.info("ConversationService initialized")

    async def create_conversation(
        self,
        title: str = "新对话",
        user_id: str = "default_user"
    ) -> Conversation:
        """创建新会话"""
        conversation = Conversation(
            title=title,
            user_id=user_id
        )
        self.conversations[conversation.id] = conversation
        logger.info(f"Created conversation: {conversation.id}")
        return conversation

    async def list_conversations(
        self,
        user_id: str = "default_user"
    ) -> List[Conversation]:
        """获取用户的会话列表"""
        conversations = [
            conv for conv in self.conversations.values()
            if conv.user_id == user_id
        ]
        # 按更新时间倒序排列
        conversations.sort(key=lambda x: x.updated_at, reverse=True)
        return conversations

    async def get_conversation(
        self,
        conv_id: str
    ) -> Optional[Conversation]:
        """获取单个会话"""
        return self.conversations.get(conv_id)

    async def update_conversation(
        self,
        conv_id: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Conversation]:
        """更新会话信息"""
        conversation = self.conversations.get(conv_id)
        if not conversation:
            return None

        if title is not None:
            conversation.title = title
        if metadata is not None:
            conversation.metadata.update(metadata)

        conversation.updated_at = datetime.now()
        logger.info(f"Updated conversation: {conv_id}")
        return conversation

    async def delete_conversation(
        self,
        conv_id: str
    ) -> bool:
        """删除会话"""
        if conv_id not in self.conversations:
            return False

        # 删除会话数据
        del self.conversations[conv_id]

        # 清除 Redis 中的历史记录
        await self.memory.clear_conversation(conv_id)

        logger.info(f"Deleted conversation: {conv_id}")
        return True

    async def add_message(
        self,
        conv_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ChatMessage]:
        """添加消息到会话"""
        conversation = self.conversations.get(conv_id)
        if not conversation:
            logger.error(f"Conversation not found: {conv_id}")
            return None

        message = ChatMessage(
            conversation_id=conv_id,
            role=role,
            content=content,
            metadata=metadata or {}
        )

        # 保存到 Redis
        await self.memory.append_message(conv_id, message)

        # 更新会话时间
        conversation.updated_at = datetime.now()

        logger.info(f"Added message to conversation {conv_id}: {role}")
        return message

    async def get_messages(
        self,
        conv_id: str,
        limit: Optional[int] = None
    ) -> List[ChatMessage]:
        """获取会话的消息历史"""
        messages = await self.memory.get_conversation_history(conv_id)

        if limit:
            messages = messages[-limit:]

        return messages

    async def generate_summary(
        self,
        conv_id: str,
        llm_service
    ) -> Optional[str]:
        """生成会话摘要

        当对话历史超过阈值时调用
        """
        messages = await self.get_messages(conv_id)

        if len(messages) < 10:  # 少于10条消息不需要摘要
            return None

        # 构建摘要 Prompt
        conversation_text = "\n".join([
            f"{'用户' if msg.role == 'user' else '助手'}: {msg.content}"
            for msg in messages[:-10]  # 只摘要早期对话
        ])

        summary_prompt = f"""请对以下对话进行简洁摘要，提取关键信息（用户需求、偏好、已讨论的内容）：

{conversation_text}

摘要（200字以内）："""

        try:
            # 调用 LLM 生成摘要
            summary = await llm_service.ainvoke(summary_prompt)

            # 保存摘要到 Redis
            await self.memory.save_conversation_summary(conv_id, summary)

            logger.info(f"Generated summary for conversation: {conv_id}")
            return summary
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return None

    async def should_generate_summary(
        self,
        conv_id: str,
        threshold: int = 20
    ) -> bool:
        """判断是否需要生成摘要"""
        messages = await self.get_messages(conv_id)
        return len(messages) >= threshold


# 全局单例
_conversation_service: Optional[ConversationService] = None


def get_conversation_service(memory_service: MemoryService) -> ConversationService:
    """获取会话服务单例"""
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService(memory_service)
    return _conversation_service
