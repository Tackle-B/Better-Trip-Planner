<template>
  <div class="trip-plan-card" @click="handleClick">
    <div class="card-header">
      <div class="card-icon">
        <EnvironmentOutlined />
      </div>
      <div class="card-title">
        <h3>{{ card.title }}</h3>
        <span class="card-subtitle">{{ card.city }} · {{ card.days_count }}天</span>
      </div>
    </div>

    <div class="card-body">
      <div class="card-dates">
        <CalendarOutlined />
        <span>{{ formatDate(card.start_date) }} - {{ formatDate(card.end_date) }}</span>
      </div>

      <div v-if="card.highlights && card.highlights.length > 0" class="card-highlights">
        <div class="highlight-label">行程亮点</div>
        <div class="highlight-tags">
          <a-tag v-for="(highlight, index) in card.highlights" :key="index" color="blue">
            {{ highlight }}
          </a-tag>
        </div>
      </div>
    </div>

    <div class="card-footer">
      <span class="view-detail">查看详情</span>
      <RightOutlined />
    </div>
  </div>
</template>

<script setup lang="ts">
import { EnvironmentOutlined, CalendarOutlined, RightOutlined } from '@ant-design/icons-vue'
import type { TripPlanCardMessage } from '@/types'
import { useRouter } from 'vue-router'

interface Props {
  card: TripPlanCardMessage
}

const props = defineProps<Props>()
const router = useRouter()

const handleClick = () => {
  router.push(`/plan/${props.card.plan_id}`)
}

const formatDate = (dateStr: string) => {
  const date = new Date(dateStr)
  return `${date.getMonth() + 1}月${date.getDate()}日`
}
</script>

<style scoped>
.trip-plan-card {
  background: #ffffff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 16px;
  margin: 12px 0;
  cursor: pointer;
  transition: all 0.3s ease;
  max-width: 500px;
}

.trip-plan-card:hover {
  border-color: #1890ff;
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.15);
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.card-icon {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 20px;
}

.card-title h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #262626;
}

.card-subtitle {
  font-size: 13px;
  color: #8c8c8c;
}

.card-body {
  margin-bottom: 12px;
}

.card-dates {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #595959;
  font-size: 14px;
  margin-bottom: 12px;
}

.card-highlights {
  margin-top: 8px;
}

.highlight-label {
  font-size: 12px;
  color: #8c8c8c;
  margin-bottom: 6px;
}

.highlight-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  color: #1890ff;
  font-size: 14px;
  padding-top: 8px;
  border-top: 1px solid #f0f0f0;
}

.view-detail {
  font-weight: 500;
}
</style>
