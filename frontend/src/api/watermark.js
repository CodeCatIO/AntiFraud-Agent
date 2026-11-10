import request from '@/utils/request'

// 嵌入水印（字段：file + watermarkText）
export function embedWatermark(formData) {
  return request.post('/watermark/embed', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// 提取水印（字段：file）
export function extractWatermark(formData) {
  return request.post('/watermark/extract', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
