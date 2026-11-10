import request from '@/utils/request'

export function createAgentCase(data) {
  return request.post('/agent/cases', data)
}

export function getAgentRun(runId) {
  return request.get(`/agent/runs/${encodeURIComponent(runId)}`)
}

export function supplementAgentRun(runId, data) {
  return request.post(`/agent/runs/${encodeURIComponent(runId)}/supplement`, data)
}

export function reviewAgentRun(runId, data) {
  return request.post(`/agent/runs/${encodeURIComponent(runId)}/review`, data)
}
