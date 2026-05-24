"""对话管理 API 路由"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import List, Optional
from ...models.schemas import (
    Conversation,
    ChatMessage,
    ConversationCreateRequest,
    ConversationUpdateRequest,
    MessageSendRequest,
    ConversationListResponse,
    MessageListResponse,
    ErrorResponse
)
from ...services.memory_service import get_memory_service
from ...services.conversation_service import get_conversation_service
from ...services.profile_service import get_profile_service
from ...agents.chat_agent import get_chat_agent
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

# 延迟初始化服务（避免模块加载时失败）
_memory_service = None
_conversation_service = None
_profile_service = None
_chat_agent = None


def get_services():
    """获取服务实例（延迟初始化）"""
    global _memory_service, _conversation_service, _profile_service, _chat_agent

    if _memory_service is None:
        _memory_service = get_memory_service()
    if _conversation_service is None:
        _conversation_service = get_conversation_service(_memory_service)
    if _profile_service is None:
        _profile_service = get_profile_service(_memory_service)
    if _chat_agent is None:
        _chat_agent = get_chat_agent(_memory_service, _profile_service)

    return _memory_service, _conversation_service, _profile_service, _chat_agent


@router.post("/", response_model=Conversation)
async def create_conversation(request: ConversationCreateRequest):
    """创建新会话"""
    try:
        _, conversation_service, _, _ = get_services()
        conversation = await conversation_service.create_conversation(
            title=request.title,
            user_id=request.user_id
        )
        return conversation
    except Exception as e:
        logger.error(f"Failed to create conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=ConversationListResponse)
async def list_conversations(
    user_id: str = Query(default="default_user", description="用户ID")
):
    """获取会话列表"""
    try:
        _, conversation_service, _, _ = get_services()
        conversations = await conversation_service.list_conversations(user_id)
        return ConversationListResponse(success=True, data=conversations)
    except Exception as e:
        logger.error(f"Failed to list conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """健康检查"""
    try:
        memory_service, _, _, _ = get_services()
        health = memory_service.health_check()
        return {
            "success": True,
            "services": health
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conv_id}/messages", response_model=MessageListResponse)
async def get_messages(
    conv_id: str,
    limit: Optional[int] = Query(default=50, description="消息数量限制")
):
    """获取会话消息历史"""
    try:
        _, conversation_service, _, _ = get_services()
        conversation = await conversation_service.get_conversation(conv_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="会话不存在")

        messages = await conversation_service.get_messages(conv_id, limit)
        return MessageListResponse(success=True, data=messages)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conv_id}/profile")
async def get_conversation_profile(conv_id: str):
    """获取会话关联的用户画像"""
    try:
        _, conversation_service, profile_service, _ = get_services()

        conversation = await conversation_service.get_conversation(conv_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="会话不存在")

        profile = await profile_service.get_user_profile(conversation.user_id)
        if not profile:
            return {"success": True, "data": None, "message": "暂无用户画像"}

        profile_summary = await profile_service.get_profile_summary(conversation.user_id)

        return {
            "success": True,
            "data": {
                "user_id": profile.user_id,
                "preferences": profile.preferences,
                "tags": profile.tags,
                "summary": profile_summary,
                "updated_at": profile.updated_at.isoformat()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conv_id}", response_model=Conversation)
async def get_conversation(conv_id: str):
    """获取单个会话"""
    try:
        _, conversation_service, _, _ = get_services()
        conversation = await conversation_service.get_conversation(conv_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="会话不存在")
        return conversation
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{conv_id}", response_model=Conversation)
async def update_conversation(conv_id: str, request: ConversationUpdateRequest):
    """更新会话（重命名）"""
    try:
        _, conversation_service, _, _ = get_services()
        conversation = await conversation_service.update_conversation(
            conv_id=conv_id,
            title=request.title
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="会话不存在")
        return conversation
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{conv_id}")
async def delete_conversation(conv_id: str):
    """删除会话"""
    try:
        _, conversation_service, _, _ = get_services()
        success = await conversation_service.delete_conversation(conv_id)
        if not success:
            raise HTTPException(status_code=404, detail="会话不存在")
        return {"success": True, "message": "会话已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{conv_id}/messages")
async def send_message(conv_id: str, request: MessageSendRequest):
    """发送消息并获取 Agent 回复（SSE 流式响应）"""
    try:
        _, conversation_service, profile_service, chat_agent = get_services()

        # 检查会话是否存在
        conversation = await conversation_service.get_conversation(conv_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="会话不存在")

        # 保存用户消息到Redis
        user_message = await conversation_service.add_message(
            conv_id=conv_id,
            role="user",
            content=request.content
        )

        if not user_message:
            raise HTTPException(status_code=500, detail="保存消息失败")

        # 流式生成 Agent 回复
        async def generate_response():
            """SSE 流式生成器"""
            assistant_response = []

            try:
                # 流式调用 Agent
                async for chunk in chat_agent.chat(
                    conv_id=conv_id,
                    user_id=request.user_id,
                    user_input=request.content
                ):
                    assistant_response.append(chunk)
                    # SSE 格式
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"

                # 保存 Agent 回复
                full_response = "".join(assistant_response)
                await conversation_service.add_message(
                    conv_id=conv_id,
                    role="assistant",
                    content=full_response
                )

                # 发送完成信号
                yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

                # 检查是否需要生成摘要
                if await conversation_service.should_generate_summary(conv_id):
                    from ...services.llm_service import get_llm
                    llm = get_llm()
                    await conversation_service.generate_summary(conv_id, llm)

                # 异步提取用户画像（不阻塞响应）
                messages = await conversation_service.get_messages(conv_id)
                if len(messages) >= 4:  # 至少2轮对话后再提取
                    from ...services.llm_service import get_llm
                    llm = get_llm()
                    await profile_service.extract_and_update_profile(
                        user_id=request.user_id,
                        messages=messages,
                        llm_service=llm
                    )

            except Exception as e:
                logger.error(f"Error in generate_response: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            generate_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        raise HTTPException(status_code=500, detail=str(e))
