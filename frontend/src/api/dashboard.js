import request from '@/utils/request'

// 仪表盘统计数据
export function getStats() {
  return request.get('/dashboard/stats')
}

// 仪表盘趋势数据
export function getTrend() {
  return request.get('/dashboard/trend')
}
