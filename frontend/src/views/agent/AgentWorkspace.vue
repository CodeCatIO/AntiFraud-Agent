<script setup>
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Refresh, Plus } from '@element-plus/icons-vue'
import { useUserStore } from '@/store/user'
import { useAgentRun } from '@/composables/useAgentRun'
import AgentCaseForm from '@/components/agent/AgentCaseForm.vue'
import AgentDraftPanel from '@/components/agent/AgentDraftPanel.vue'
import AgentReviewPanel from '@/components/agent/AgentReviewPanel.vue'
import AgentRunProgress from '@/components/agent/AgentRunProgress.vue'
import AgentRunTimeline from '@/components/agent/AgentRunTimeline.vue'
import AgentSupplementPanel from '@/components/agent/AgentSupplementPanel.vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const { run, loading, submitting, loadRun, createRun, submitSupplement, submitReview, resetRun } = useAgentRun()

const events = computed(() => run.value?.events || [])
const supplements = computed(() => run.value?.supplements || [])
const draft = computed(() => run.value?.result || {})
const canReview = computed(() => userStore.canReviewAgentRuns)
const waitingInfoEvent = computed(() => [...events.value].reverse().find((event) => event.eventType === 'run.waiting_for_info'))
const waitingInfo = computed(() => parsePayload(waitingInfoEvent.value?.payloadJson))
const showDraft = computed(() => Object.keys(draft.value).length > 0)
const statusLabel = computed(() => ({
  QUEUED: '排队中',
  RUNNING: '执行中',
  WAITING_FOR_INFO: '等待补充信息',
  WAITING_FOR_REVIEW: '等待人工审核',
  COMPLETED: '已完成',
  PARTIAL: '部分完成',
  RETURNED: '已退回',
  FAILED: '执行失败',
  CANCELLED: '已取消',
}[run.value?.status] || run.value?.status || ''))
const statusType = computed(() => ({
  WAITING_FOR_INFO: 'warning',
  WAITING_FOR_REVIEW: 'warning',
  COMPLETED: 'success',
  PARTIAL: 'warning',
  FAILED: 'danger',
  RETURNED: 'info',
}[run.value?.status] || 'primary'))

function parsePayload(value) {
  if (value && typeof value === 'object') return value
  try { return JSON.parse(value || '{}') } catch { return {} }
}

async function handleCreate(payload) {
  try {
    const created = await createRun(payload)
    if (created?.runId) {
      await router.replace({ path: '/agent', query: { runId: created.runId } })
    }
  } catch {
    return
  }
}

async function handleSupplement(payload) {
  try { await submitSupplement(payload) } catch { return }
}

async function handleReview(payload) {
  try { await submitReview(payload) } catch { return }
}

async function refresh() {
  if (!run.value?.runId) return
  try { await loadRun(run.value.runId) } catch { return }
}

function scrollToReview() {
  document.getElementById('agent-review')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function newCase() {
  resetRun()
  router.replace({ path: '/agent' })
}

onMounted(() => {
  if (typeof route.query.runId === 'string') loadRun(route.query.runId).catch(() => {})
})
</script>

<template>
  <main class="agent-workspace">
    <header class="page-heading">
      <div><span class="eyebrow">CASE REVIEW WORKSPACE</span><h1>反诈线索研判</h1><p>受控工具调用、来源可回查、人工决定留痕；系统不自动报警或执行外部操作。</p></div>
      <div class="heading-actions">
        <el-button v-if="run" :icon="Plus" plain @click="newCase">新建任务</el-button>
        <el-button v-if="run" :icon="Refresh" :loading="loading" plain @click="refresh">刷新状态</el-button>
        <el-button v-if="run?.status === 'WAITING_FOR_REVIEW' && canReview" type="primary" @click="scrollToReview">去提审</el-button>
      </div>
    </header>

    <AgentRunProgress
      v-if="run"
      class="workspace-progress"
      :status="run.status"
      :events="events"
      :supplements="supplements"
    />

    <div class="workspace-grid">
      <div class="left-column">
        <AgentCaseForm v-if="!run" :busy="submitting" @submit="handleCreate" />
        <section v-if="run" class="run-overview panel">
          <div class="run-title"><div><span>ACTIVE RUN</span><h2>任务状态</h2></div><el-tag :type="statusType" effect="light">{{ statusLabel }}</el-tag></div>
          <dl><div><dt>案件编号</dt><dd>{{ run.caseNo || run.caseId }}</dd></div><div><dt>运行 ID</dt><dd class="run-id">{{ run.runId }}</dd></div></dl>
          <div v-if="run.content" class="source-text"><h3>提交线索</h3><p>{{ run.content }}</p></div>
        </section>
        <AgentSupplementPanel
          v-if="run?.status === 'WAITING_FOR_INFO'"
          :round="Number(waitingInfo.round || 1)"
          :questions="waitingInfo.questions || []"
          :busy="submitting"
          @submit="handleSupplement"
        />
        <AgentDraftPanel v-if="showDraft" :draft="draft" />
        <section v-if="run?.status === 'WAITING_FOR_REVIEW' && !canReview" class="review-hint">
          本次研判等待具备审核权限的用户处理。提交人不能审核自己的案件。
        </section>
        <AgentReviewPanel
          v-if="run?.status === 'WAITING_FOR_REVIEW' && canReview"
          id="agent-review"
          :busy="submitting"
          @submit="handleReview"
        />
      </div>

      <aside class="right-column">
        <AgentRunTimeline :events="events" />
        <section class="safety-panel">
          <span class="safety-mark">i</span>
          <div><strong>研判边界</strong><p>自动检测和知识检索仅作为线索。引用为来源卡转述，需打开原始来源核对；最终结论由授权人员确认。</p></div>
        </section>
      </aside>
    </div>
  </main>
</template>

<style scoped lang="scss">
.agent-workspace { max-width: 1500px; margin: 0 auto; }
.page-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 22px; margin: 2px 0 24px; .eyebrow { color: #197f7a; font-size: 10px; font-weight: 700; letter-spacing: .13em; } h1 { margin: 6px 0 0; color: #18394c; font-size: 28px; letter-spacing: -.025em; } p { max-width: 700px; margin: 8px 0 0; color: #667d88; font-size: 13px; line-height: 1.7; } }
.heading-actions { display: flex; flex: none; gap: 10px; }
.workspace-progress { margin-bottom: 18px; }
.workspace-grid { display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(290px, .8fr); align-items: start; gap: 20px; }
.left-column, .right-column { display: flex; min-width: 0; flex-direction: column; gap: 16px; }
.panel { border: 1px solid #dce9e8; border-radius: 16px; background: #fff; box-shadow: 0 14px 34px rgba(24, 63, 73, .055); }
.run-overview { padding: 20px 23px; }
.run-title { display: flex; align-items: center; justify-content: space-between; gap: 12px; span { color: #1a817c; font-size: 10px; font-weight: 700; letter-spacing: .12em; } h2 { margin: 4px 0 0; color: #19384a; font-size: 17px; } }
.run-overview dl { display: grid; grid-template-columns: minmax(120px, .6fr) minmax(0, 1.4fr); gap: 14px; margin: 17px 0 0; padding-top: 15px; border-top: 1px solid #e7efee; div { min-width: 0; } dt { color: #829198; font-size: 11px; } dd { margin: 5px 0 0; color: #35515e; font-size: 12px; overflow-wrap: anywhere; } }
.run-id { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
.source-text { margin-top: 16px; padding-top: 14px; border-top: 1px solid #e7efee; h3 { margin: 0 0 7px; color: #526d77; font-size: 12px; } p { max-height: 170px; margin: 0; overflow: auto; color: #526a74; font-size: 12px; line-height: 1.7; white-space: pre-wrap; overflow-wrap: anywhere; } }
.review-hint { padding: 15px 17px; border: 1px solid #e8dfc9; border-radius: 12px; background: #fffaf0; color: #756744; font-size: 12px; line-height: 1.7; }
.safety-panel { display: flex; gap: 11px; padding: 15px 16px; border: 1px solid #d8e8e5; border-radius: 13px; background: #edf7f4; .safety-mark { display: grid; width: 20px; height: 20px; flex: none; place-items: center; border-radius: 50%; background: #d4ece6; color: #327f75; font-size: 12px; font-weight: 700; } strong { color: #31564f; font-size: 12px; } p { margin: 5px 0 0; color: #648078; font-size: 11px; line-height: 1.65; } }
@media (max-width: 1000px) { .workspace-grid { grid-template-columns: 1fr; } .right-column { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(220px, .8fr); align-items: start; } }
@media (max-width: 640px) { .page-heading { align-items: flex-start; flex-direction: column; h1 { font-size: 24px; } } .heading-actions { width: 100%; } .heading-actions .el-button { flex: 1; } .right-column { display: flex; } .run-overview dl { grid-template-columns: 1fr; } }
</style>
