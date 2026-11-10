import request from '@/utils/request'

// 文本检测（后端 DetectController 读取 content 字段）
export function detectText(text) {
  return request.post('/detect/text', { content: text })
}

// 语音检测（multipart/form-data）
export function detectVoice(formData) {
  return request.post('/detect/voice', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// 图片检测（multipart/form-data）
export function detectImage(formData) {
  return request.post('/detect/image', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// 检测记录列表（支持分页和筛选参数）
export function getRecords(params) {
  return request.get('/detect/records', { params })
}

// 检测记录详情
export function getRecordDetail(id) {
  return request.get(`/detect/records/${id}`)
}
