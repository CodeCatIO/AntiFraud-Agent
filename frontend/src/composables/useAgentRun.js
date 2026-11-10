import { onUnmounted, shallowRef } from 'vue'
import {
  createAgentCase,
  getAgentRun,
  reviewAgentRun,
  supplementAgentRun,
} from '@/api/agent'

const ACTIVE_STATUSES = new Set(['QUEUED', 'RUNNING'])

export function useAgentRun() {
  const run = shallowRef(null)
  const loading = shallowRef(false)
  const submitting = shallowRef(false)
  let pollTimer = null

  function stopPolling() {
    if (pollTimer) {
      clearTimeout(pollTimer)
      pollTimer = null
    }
  }

  function schedulePoll(runId, status) {
    stopPolling()
    if (!ACTIVE_STATUSES.has(status)) return
    pollTimer = setTimeout(() => loadRun(runId, true), 1800)
  }

  async function loadRun(runId, silent = false) {
    if (!runId) return null
    stopPolling()
    if (!silent) loading.value = true
    try {
      const latest = await getAgentRun(runId)
      run.value = latest
      schedulePoll(runId, latest?.status)
      return latest
    } finally {
      if (!silent) loading.value = false
    }
  }

  async function createRun(payload) {
    submitting.value = true
    try {
      const created = await createAgentCase(payload)
      if (created?.runId) await loadRun(created.runId, true)
      return created
    } finally {
      submitting.value = false
    }
  }

  async function submitSupplement(payload) {
    if (!run.value?.runId) return
    submitting.value = true
    try {
      await supplementAgentRun(run.value.runId, payload)
      await loadRun(run.value.runId, true)
    } finally {
      submitting.value = false
    }
  }

  async function submitReview(payload) {
    if (!run.value?.runId) return
    submitting.value = true
    try {
      await reviewAgentRun(run.value.runId, payload)
      await loadRun(run.value.runId, true)
    } finally {
      submitting.value = false
    }
  }

  function resetRun() {
    stopPolling()
    run.value = null
  }

  onUnmounted(stopPolling)

  return { run, loading, submitting, loadRun, createRun, submitSupplement, submitReview, resetRun }
}
