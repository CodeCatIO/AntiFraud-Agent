<script setup>
import { computed } from 'vue'

const props = defineProps({ events: { type: Array, default: () => [] } })

const eventLabels = {
  'run.started': '任务已受理',
  'step.completed': '只读工具执行完成',
  'run.waiting_for_info': '等待补充线索',
  'run.waiting_for_review': '草稿等待人工审核',
  'run.finished': '本次研判已结束',
  'dispatch.failed': '任务启动失败',
}

const entries = computed(() => [...props.events].sort((left, right) => left.eventSeq - right.eventSeq))

function parsePayload(value) {
  if (value && typeof value === 'object') return value
  try { return JSON.parse(value || '{}') } catch { return {} }
}

function formatTime(value) {
  if (!value) return '时间未记录'
  return String(value).replace('T', ' ').replace('Z', '').slice(0, 19)
}

function eventDetail(event) {
  const payload = parsePayload(event.payloadJson)
  if (event.eventType === 'step.completed') {
    const calls = Array.isArray(payload.toolCalls) ? payload.toolCalls : []
    return calls.map((call) => `${call.tool || '只读工具'} · ${call.status || '已执行'}`).join('；') || '检测与知识检索已返回。'
  }
  if (event.eventType === 'run.waiting_for_info') return `待补充 ${payload.questions?.length || 0} 项信息。`
  if (event.eventType === 'run.finished') return `状态：${event.status || '完成'}。`
  if (event.eventType === 'dispatch.failed') return `错误码：${payload.errorCode || 'DISPATCH_FAILED'}`
  return event.status || '工作流状态已记录。'
}
</script>

<template>
  <section class="timeline-panel panel">
    <header class="section-title"><div><span>RUN TRACE</span><h2>执行轨迹</h2></div><span class="event-count">{{ events.length }} 条事件</span></header>
    <el-empty v-if="!entries.length" description="任务事件尚未到达" :image-size="54" />
    <el-timeline v-else class="run-timeline">
      <el-timeline-item v-for="event in entries" :key="event.eventSeq" :timestamp="formatTime(event.occurredAt)" placement="top" color="#248b83">
        <div class="event-heading"><strong>{{ eventLabels[event.eventType] || event.eventType }}</strong><el-tag size="small" effect="plain">#{{ event.eventSeq }}</el-tag></div>
        <p>{{ eventDetail(event) }}</p>
      </el-timeline-item>
    </el-timeline>
  </section>
</template>

<style scoped lang="scss">
.panel { border: 1px solid #dce9e8; border-radius: 16px; background: #fff; box-shadow: 0 14px 34px rgba(24, 63, 73, .055); }
.timeline-panel { padding: 23px 24px 8px; }
.section-title { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; span:first-child { color: #1a817c; font-size: 10px; font-weight: 700; letter-spacing: .12em; } h2 { margin: 4px 0 0; color: #19384a; font-size: 18px; } }
.event-count { color: #7c8e95; font-size: 12px; }
.run-timeline { padding: 0 2px; }
.event-heading { display: flex; align-items: center; justify-content: space-between; gap: 10px; color: #294957; font-size: 13px; }
.run-timeline p { margin: 6px 0 0; color: #73838c; font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; }
</style>
