import axios from 'axios'
import type { TripFormData, TripPlanResponse, SavedTripPlan, TripPlan } from '@/types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000, // 2分钟超时
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    console.log('发送请求:', config.method?.toUpperCase(), config.url)
    return config
  },
  (error) => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => {
    console.log('收到响应:', response.status, response.config.url)
    return response
  },
  (error) => {
    console.error('响应错误:', error.response?.status, error.message)
    return Promise.reject(error)
  }
)

/**
 * 生成旅行计划
 */
export async function generateTripPlan(formData: TripFormData): Promise<TripPlanResponse> {
  try {
    const response = await apiClient.post<TripPlanResponse>('/api/trip/plan', formData)
    return response.data
  } catch (error: any) {
    console.error('生成旅行计划失败:', error)
    throw new Error(error.response?.data?.detail || error.message || '生成旅行计划失败')
  }
}

/**
 * 健康检查
 */
export async function healthCheck(): Promise<any> {
  try {
    const response = await apiClient.get('/health')
    return response.data
  } catch (error: any) {
    console.error('健康检查失败:', error)
    throw new Error(error.message || '健康检查失败')
  }
}

// ============ 对话管理 API ============

/**
 * 创建新会话
 */
export async function createConversation(title: string = '新对话', userId: string = 'default_user') {
  const response = await apiClient.post('/api/conversations/', {
    title,
    user_id: userId
  })
  return response.data
}

/**
 * 获取会话列表
 */
export async function listConversations(userId: string = 'default_user') {
  const response = await apiClient.get('/api/conversations/', {
    params: { user_id: userId }
  })
  return response.data
}

/**
 * 获取单个会话
 */
export async function getConversation(convId: string) {
  const response = await apiClient.get(`/api/conversations/${convId}`)
  return response.data
}

/**
 * 更新会话（重命名）
 */
export async function updateConversation(convId: string, title: string) {
  const response = await apiClient.patch(`/api/conversations/${convId}`, {
    title
  })
  return response.data
}

/**
 * 删除会话
 */
export async function deleteConversation(convId: string) {
  const response = await apiClient.delete(`/api/conversations/${convId}`)
  return response.data
}

/**
 * 发送消息（SSE 流式响应）
 */
export async function* sendMessage(
  convId: string,
  content: string,
  userId: string = 'default_user'
): AsyncGenerator<string> {
  const response = await fetch(`${API_BASE_URL}/api/conversations/${convId}/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      content,
      user_id: userId
    })
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    const chunk = decoder.decode(value)
    const lines = chunk.split('\n')

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6)
        try {
          const parsed = JSON.parse(data)
          if (parsed.type === 'chunk') {
            yield parsed.content
          } else if (parsed.type === 'error') {
            throw new Error(parsed.message)
          } else if (parsed.type === 'done') {
            return
          }
        } catch (e) {
          // 忽略解析错误
        }
      }
    }
  }
}

/**
 * 获取会话消息历史
 */
export async function getMessages(convId: string, limit?: number) {
  const response = await apiClient.get(`/api/conversations/${convId}/messages`, {
    params: limit ? { limit } : {}
  })
  return response.data
}

/**
 * 获取会话关联的用户画像
 */
export async function getConversationProfile(convId: string) {
  const response = await apiClient.get(`/api/conversations/${convId}/profile`)
  return response.data
}

// ============ 旅行计划管理 API ============

/**
 * 保存旅行计划
 */
export async function saveTripPlan(
  title: string,
  plan: TripPlan,
  userId: string = 'default_user',
  conversationId?: string
) {
  const response = await apiClient.post('/api/plans', {
    title,
    plan,
    user_id: userId,
    conversation_id: conversationId
  })
  return response.data
}

/**
 * 获取旅行计划详情
 */
export async function getTripPlan(planId: string): Promise<{ success: boolean; data: SavedTripPlan }> {
  const response = await apiClient.get(`/api/plans/${planId}`)
  return response.data
}

/**
 * 更新旅行计划
 */
export async function updateTripPlan(
  planId: string,
  updates: { title?: string; plan?: TripPlan }
) {
  const response = await apiClient.put(`/api/plans/${planId}`, updates)
  return response.data
}

/**
 * 删除旅行计划
 */
export async function deleteTripPlan(planId: string) {
  const response = await apiClient.delete(`/api/plans/${planId}`)
  return response.data
}

/**
 * 列出旅行计划
 */
export async function listTripPlans(
  userId?: string,
  conversationId?: string,
  limit: number = 50
) {
  const response = await apiClient.get('/api/plans', {
    params: { user_id: userId, conversation_id: conversationId, limit }
  })
  return response.data
}

export default apiClient


