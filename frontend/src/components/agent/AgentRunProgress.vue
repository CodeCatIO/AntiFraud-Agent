<script setup>
import { computed } from 'vue'
import { Check, Clock, Loading, WarningFilled } from '@element-plus/icons-vue'

const props = defineProps({
  status: { type: String, default: '' },
  events: { type: Array, default: () => [] },
  supplements: { type: Array, default: () => [] },
})

const STEPS = [
  { key: 'accepted', label: '提交受理', hint: '校验线索并创建任务' },
  { key: 'supplement', label: '信息补全', hint: '缺失要素按轮追问' },
  { key: 'analysis', label: '智能研判', hint: '只读检测与知识检索' },
  { key: 'review', label: '人工复核', hint: '授权人员确认草稿' },
  { key: 'archived', label: '归档完成', hint: '结论与审核留痕' },
]

const TERMINAL = new Set(['COMPLETED', 'PARTIAL', 'RETURNED', 'FAILED', 'CANCELLED'])

const hasEvent = (type) => props.events.some((event) => event.eventType === type)

const activeIndex = computed(() => {
  if (TERMINAL.has(props.status)) return 4
  if (props.status === 'WAITING_FOR_REVIEW') return 3
  if (props.status === 'WAITING_FOR_INFO') return 1
  if (hasEvent('step.completed')) return 3
  if (props.status === 'RUNNING') return 2
  return 0
})

const failed = computed(() => props.status === 'FAILED' || props.status === 'CANCELLED')
const progressPercent = computed(() => {
  if (failed.value) return Math.max(8, Math.round((activeIndex.value / (STEPS.length - 1)) * 100))
  return Math.max(6, Math.round((activeIndex.value / (STEPS.length - 1)) * 100))
})

const supplementRounds = computed(() => props.supplements?.length || 0)

function stepState(index) {
  if (index < activeIndex.value) return 'done'
  if (index === activeIndex.value) return failed.value && index === 3 ? 'error' : 'current'
  return 'pending'
}

function stepIcon(index) {
  const state = stepState(index)
  if (state === 'done') return Check
  if (state === 'error') return WarningFilled
  if (state === 'current') return props.status === 'RUNNING' || props.status === 'QUEUED' ? Loading : Clock
  return null
}

function stepNote(index) {
  if (index === 1 && supplementRounds.value) return `已补充 ${supplementRounds.value} 轮`
  if (index === 3 && props.status === 'WAITING_FOR_REVIEW') return '等待审核人处理'
  if (index === 4 && TERMINAL.has(props.status)) return statusText.value
  return STEPS[index].hint
}

const statusText = computed(() => ({
  QUEUED: '排队中',
  RUNNING: '执行中',
  WAITING_FOR_INFO: '待补充',
  WAITING_FOR_REVIEW: '待审核',
  COMPLETED: '已完成',
  PARTIAL: '部分完成',
  RETURNED: '已退回',
  FAILED: '执行失败',
  CANCELLED: '已取消',
}[props.status] || '未开始'))
</script>

<template>
  <section class="run-progress panel" aria-label="研判进度">
    <header class="progress-head">
      <div>
        <span>WORKFLOW PROGRESS</span>
        <h2>研判进度 <small>{{ statusText }}</small></h2>
      </div>
      <div class="progress-figure">
        <strong>{{ progressPercent }}%</strong>
        <span>{{ supplementRounds ? `补充 ${supplementRounds} 轮` : '单轮研判' }}</span>
      </div>
    </header>

    <div class="progress-track" role="progressbar" :aria-valuenow="progressPercent" aria-valuemin="0" aria-valuemax="100">
      <span class="progress-fill" :class="{ failed }" :style="{ width: `${progressPercent}%` }" />
    </div>

    <ol class="step-list">
      <li v-for="(step, index) in STEPS" :key="step.key" :class="stepState(index)">
        <span class="step-dot">
          <el-icon v-if="stepIcon(index)" :class="{ spin: stepIcon(index) === Loading }"><component :is="stepIcon(index)" /></el-icon>
          <template v-else>{{ index + 1 }}</template>
        </span>
        <div class="step-text">
          <strong>{{ step.label }}</strong>
          <span>{{ stepNote(index) }}</span>
        </div>
      </li>
    </ol>
  </section>
</template>

<style scoped lang="scss">
.panel { border: 1px solid #dce9e8; border-radius: 16px; background: #fff; box-shadow: 0 14px 34px rgba(24, 63, 73, .055); }
.run-progress { padding: 20px 23px 18px; }
.progress-head { display: flex; align-items: center; justify-content: space-between; gap: 14px; span { color: #1a817c; font-size: 10px; font-weight: 700; letter-spacing: .12em; } h2 { margin: 4px 0 0; color: #19384a; font-size: 17px; } small { margin-left: 8px; color: #6f858d; font-size: 12px; font-weight: 500; } }
.progress-figure { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; strong { color: #167b81; font-size: 22px; line-height: 1; } span { color: #829198; font-size: 11px; } }
.progress-track { height: 6px; margin: 17px 0 18px; overflow: hidden; border-radius: 99px; background: #ecf2f2; }
.progress-fill { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #2aa39d, #167b81); transition: width .45s ease; }
.progress-fill.failed { background: linear-gradient(90deg, #e0915a, #d3574f); }
.step-list { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; margin: 0; padding: 0; list-style: none; }
.step-list li { display: flex; min-width: 0; gap: 8px; }
.step-dot { display: grid; width: 24px; height: 24px; flex: none; place-items: center; border: 1px solid #d9e5e4; border-radius: 50%; background: #f6faf9; color: #9aa9ac; font-size: 11px; font-weight: 700; }
.step-text { min-width: 0; display: flex; flex-direction: column; gap: 3px; strong { color: #6d8088; font-size: 12px; } span { color: #93a1a5; font-size: 10px; line-height: 1.45; } }
li.done .step-dot { border-color: #167b81; background: #167b81; color: #fff; }
li.done .step-text strong { color: #2c5a63; }
li.current .step-dot { border-color: #2aa39d; background: #e9f7f5; color: #167b81; box-shadow: 0 0 0 4px rgba(42, 163, 157, .12); }
li.current .step-text strong { color: #19384a; }
li.error .step-dot { border-color: #d3574f; background: #fdeeec; color: #c64c45; }
li.error .step-text strong { color: #a8423c; }
.spin { animation: spin 1.2s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 900px) { .step-list { grid-template-columns: repeat(3, minmax(0, 1fr)); row-gap: 14px; } }
@media (max-width: 560px) { .run-progress { padding: 17px; } .step-list { grid-template-columns: 1fr; } .step-text span { display: none; } }
@media (prefers-reduced-motion: reduce) { .progress-fill { transition: none; } .spin { animation: none; } }
</style>
