<template>
  <div class="chat-container">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <h1 class="app-title">旅行助手</h1>
        <button class="new-chat-btn" @click="createNewChat">
          <span class="icon">+</span>
          新对话
        </button>
      </div>

      <div class="conversation-list">
        <div
          v-for="conv in conversations"
          :key="conv.id"
          :class="['conversation-item', { active: conv.id === currentConversationId }]"
          @click="selectConversation(conv.id)"
        >
          <div class="conversation-content">
            <span class="conversation-title">{{ conv.title }}</span>
            <span class="conversation-time">{{ formatTime(conv.updated_at) }}</span>
          </div>
          <div class="conversation-actions">
            <button class="action-btn" @click.stop="renameConversation(conv)" title="重命名">
              ✏️
            </button>
            <button class="action-btn" @click.stop="deleteConversation(conv.id)" title="删除">
              🗑️
            </button>
          </div>
        </div>

        <div v-if="conversations.length === 0" class="empty-state">
          暂无对话，点击上方按钮开始新对话
        </div>
      </div>
    </aside>

    <!-- 聊天区域 -->
    <main class="chat-area">
      <div v-if="!currentConversationId" class="welcome-screen">
        <h2>欢迎使用智能旅行助手</h2>
        <p>开始新对话，让我帮您规划完美的旅行</p>
      </div>

      <div v-else class="chat-content">
        <!-- 消息列表 -->
        <div class="messages-container" ref="messagesContainer">
          <div
            v-for="message in messages"
            :key="message.id"
            :class="['message', message.role]"
          >
            <div class="message-bubble">
              <div class="message-content">
                <template v-for="(part, index) in parseMessageContent(message.content)" :key="index">
                  <TripPlanCard v-if="part.type === 'card'" :card="part.data" />
                  <div v-else v-html="formatMessage(part.text)"></div>
                </template>
              </div>
              <div class="message-time">{{ formatTime(message.timestamp) }}</div>
            </div>
          </div>

          <div v-if="isLoading" class="message assistant">
            <div class="message-bubble">
              <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        </div>

        <!-- 输入框 -->
        <div class="input-area">
          <textarea
            v-model="inputText"
            class="message-input"
            placeholder="输入您的旅行需求，例如：我想去北京玩三天..."
            @keydown.enter.exact.prevent="sendMessage"
            @keydown.enter.shift.exact="inputText += '\n'"
            :disabled="isLoading"
          ></textarea>
          <button
            class="send-btn"
            @click="sendMessage"
            :disabled="!inputText.trim() || isLoading"
          >
            发送
          </button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import * as api from '../services/api'
import TripPlanCard from '../components/TripPlanCard.vue'
import type { TripPlanCardMessage } from '@/types'

const router = useRouter()
const route = useRoute()

// 状态
const conversations = ref<any[]>([])
const currentConversationId = ref<string | null>(null)
const messages = ref<any[]>([])
const inputText = ref('')
const isLoading = ref(false)
const messagesContainer = ref<HTMLElement | null>(null)

// 加载会话列表
const loadConversations = async () => {
  try {
    const response = await api.listConversations()
    conversations.value = response.data
  } catch (error) {
    console.error('Failed to load conversations:', error)
  }
}

// 创建新对话
const createNewChat = async () => {
  try {
    const conversation = await api.createConversation('新对话')
    conversations.value.unshift(conversation)
    selectConversation(conversation.id)
  } catch (error) {
    console.error('Failed to create conversation:', error)
    alert('创建对话失败')
  }
}

// 选择对话
const selectConversation = async (convId: string) => {
  currentConversationId.value = convId
  router.push(`/chat/${convId}`)
  await loadMessages(convId)
}

// 加载消息
const loadMessages = async (convId: string) => {
  try {
    const response = await api.getMessages(convId)
    messages.value = response.data
    await nextTick()
    scrollToBottom()
  } catch (error) {
    console.error('Failed to load messages:', error)
  }
}

// 发送消息
const sendMessage = async () => {
  if (!inputText.value.trim() || isLoading.value || !currentConversationId.value) {
    return
  }

  const userMessage = {
    id: Date.now().toString(),
    conversation_id: currentConversationId.value,
    role: 'user',
    content: inputText.value.trim(),
    timestamp: new Date().toISOString()
  }

  messages.value.push(userMessage)
  const messageContent = inputText.value.trim()
  inputText.value = ''
  isLoading.value = true

  await nextTick()
  scrollToBottom()

  try {
    let assistantContent = ''
    const assistantMessage = {
      id: (Date.now() + 1).toString(),
      conversation_id: currentConversationId.value,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString()
    }
    messages.value.push(assistantMessage)

    // 流式接收
    try {
      for await (const chunk of api.sendMessage(currentConversationId.value, messageContent)) {
        assistantContent += chunk
        assistantMessage.content = assistantContent
        await nextTick()
        scrollToBottom()
      }
    } catch (streamError) {
      console.error('Stream error:', streamError)
      // 如果流式接收出错，在消息中显示错误
      assistantMessage.content = assistantContent + '\n\n[错误] 接收消息时出现问题，请重试。'
    }

    // 更新会话列表
    await loadConversations()
  } catch (error) {
    console.error('Failed to send message:', error)
    // 在聊天界面显示错误消息，而不是弹窗
    const errorMessage = {
      id: (Date.now() + 2).toString(),
      conversation_id: currentConversationId.value,
      role: 'assistant',
      content: '抱歉，发送消息失败。请检查网络连接后重试。',
      timestamp: new Date().toISOString()
    }
    messages.value.push(errorMessage)
  } finally {
    isLoading.value = false
  }
}

// 重命名对话
const renameConversation = async (conv: any) => {
  const newTitle = prompt('请输入新标题', conv.title)
  if (newTitle && newTitle.trim()) {
    try {
      await api.updateConversation(conv.id, newTitle.trim())
      conv.title = newTitle.trim()
    } catch (error) {
      console.error('Failed to rename conversation:', error)
      alert('重命名失败')
    }
  }
}

// 删除对话
const deleteConversation = async (convId: string) => {
  if (!confirm('确定要删除这个对话吗？')) {
    return
  }

  try {
    await api.deleteConversation(convId)
    conversations.value = conversations.value.filter(c => c.id !== convId)
    if (currentConversationId.value === convId) {
      currentConversationId.value = null
      messages.value = []
      router.push('/chat')
    }
  } catch (error) {
    console.error('Failed to delete conversation:', error)
    alert('删除失败')
  }
}

// 格式化时间
const formatTime = (timestamp: string) => {
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  if (diff < 604800000) return `${Math.floor(diff / 86400000)}天前`

  return date.toLocaleDateString('zh-CN')
}

// 格式化消息（支持 Markdown）
const formatMessage = (content: string) => {
  // 简单的 Markdown 转换
  return content
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br>')
    .replace(/^# (.*?)$/gm, '<h1>$1</h1>')
    .replace(/^## (.*?)$/gm, '<h2>$1</h2>')
    .replace(/^### (.*?)$/gm, '<h3>$1</h3>')
    .replace(/^- (.*?)$/gm, '<li>$1</li>')
}

// 解析消息内容，提取旅行计划卡片
const parseMessageContent = (content: string): Array<{ type: 'text' | 'card'; text?: string; data?: TripPlanCardMessage }> => {
  const parts: Array<{ type: 'text' | 'card'; text?: string; data?: TripPlanCardMessage }> = []

  // 匹配 [TRIP_PLAN_CARD]...[/TRIP_PLAN_CARD] 标记
  const cardRegex = /\[TRIP_PLAN_CARD\](.*?)\[\/TRIP_PLAN_CARD\]/gs
  let lastIndex = 0
  let match

  while ((match = cardRegex.exec(content)) !== null) {
    // 添加卡片前的文本
    if (match.index > lastIndex) {
      const text = content.substring(lastIndex, match.index).trim()
      if (text) {
        parts.push({ type: 'text', text })
      }
    }

    // 解析卡片数据
    try {
      const cardData = JSON.parse(match[1]) as TripPlanCardMessage
      parts.push({ type: 'card', data: cardData })
    } catch (e) {
      console.error('Failed to parse trip plan card:', e)
      // 如果解析失败，当作普通文本
      parts.push({ type: 'text', text: match[0] })
    }

    lastIndex = cardRegex.lastIndex
  }

  // 添加剩余文本
  if (lastIndex < content.length) {
    const text = content.substring(lastIndex).trim()
    if (text) {
      parts.push({ type: 'text', text })
    }
  }

  // 如果没有找到任何卡片，返回整个内容作为文本
  if (parts.length === 0) {
    parts.push({ type: 'text', text: content })
  }

  return parts
}

// 滚动到底部
const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// 监听路由变化
watch(() => route.params.conversationId, (newId) => {
  if (newId && typeof newId === 'string') {
    currentConversationId.value = newId
    loadMessages(newId)
  }
})

// 初始化
onMounted(async () => {
  await loadConversations()

  // 如果 URL 中有会话 ID，加载该会话
  const convId = route.params.conversationId
  if (convId && typeof convId === 'string') {
    currentConversationId.value = convId
    await loadMessages(convId)
  }
})
</script>

<style scoped>
.chat-container {
  display: flex;
  height: 100vh;
  background: #ffffff;
}

/* 侧边栏 */
.sidebar {
  width: 280px;
  background: #f8f9fa;
  border-right: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid #e5e7eb;
}

.app-title {
  font-size: 20px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 16px;
}

.new-chat-btn {
  width: 100%;
  padding: 10px 16px;
  background: #ffffff;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 14px;
  color: #374151;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s;
}

.new-chat-btn:hover {
  background: #f3f4f6;
  border-color: #9ca3af;
}

.new-chat-btn .icon {
  font-size: 18px;
  font-weight: 300;
}

.conversation-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.conversation-item {
  padding: 12px;
  margin-bottom: 4px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.conversation-item:hover {
  background: #e5e7eb;
}

.conversation-item.active {
  background: #ffffff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.conversation-content {
  flex: 1;
  min-width: 0;
}

.conversation-title {
  display: block;
  font-size: 14px;
  color: #1f2937;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conversation-time {
  display: block;
  font-size: 12px;
  color: #9ca3af;
  margin-top: 4px;
}

.conversation-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.conversation-item:hover .conversation-actions {
  opacity: 1;
}

.action-btn {
  padding: 4px 8px;
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 14px;
  border-radius: 4px;
  transition: background 0.2s;
}

.action-btn:hover {
  background: #d1d5db;
}

.empty-state {
  padding: 40px 20px;
  text-align: center;
  color: #9ca3af;
  font-size: 14px;
  line-height: 1.6;
}

/* 聊天区域 */
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #ffffff;
}

.welcome-screen {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #6b7280;
}

.welcome-screen h2 {
  font-size: 24px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 12px;
}

.welcome-screen p {
  font-size: 16px;
}

.chat-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.message {
  display: flex;
  margin-bottom: 16px;
}

.message.user {
  justify-content: flex-end;
}

.message.assistant {
  justify-content: flex-start;
}

.message-bubble {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 12px;
}

.message.user .message-bubble {
  background: #f3f4f6;
  color: #1f2937;
}

.message.assistant .message-bubble {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  color: #1f2937;
}

.message-content {
  font-size: 15px;
  line-height: 1.6;
  word-wrap: break-word;
}

.message-content :deep(h1) {
  font-size: 20px;
  font-weight: 600;
  margin: 16px 0 8px;
}

.message-content :deep(h2) {
  font-size: 18px;
  font-weight: 600;
  margin: 14px 0 6px;
}

.message-content :deep(h3) {
  font-size: 16px;
  font-weight: 600;
  margin: 12px 0 4px;
}

.message-content :deep(li) {
  margin-left: 20px;
  list-style: disc;
}

.message-time {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 6px;
}

.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 8px 0;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: #9ca3af;
  border-radius: 50%;
  animation: typing 1.4s infinite;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 60%, 100% {
    opacity: 0.3;
  }
  30% {
    opacity: 1;
  }
}

/* 输入区域 */
.input-area {
  padding: 20px 24px;
  border-top: 1px solid #e5e7eb;
  display: flex;
  gap: 12px;
  background: #ffffff;
}

.message-input {
  flex: 1;
  padding: 12px 16px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 15px;
  font-family: inherit;
  resize: none;
  min-height: 48px;
  max-height: 120px;
  outline: none;
  transition: border-color 0.2s;
}

.message-input:focus {
  border-color: #9ca3af;
}

.message-input:disabled {
  background: #f9fafb;
  cursor: not-allowed;
}

.send-btn {
  padding: 12px 24px;
  background: #1f2937;
  color: #ffffff;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.send-btn:hover:not(:disabled) {
  background: #111827;
}

.send-btn:disabled {
  background: #d1d5db;
  cursor: not-allowed;
}
</style>
