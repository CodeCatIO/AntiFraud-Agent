import request from '@/utils/request'

// 文件上传
export function uploadFile(formData) {
  return request.post('/file/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// 文件下载
export function downloadFile(id) {
  return request.get(`/file/${id}`, {
    responseType: 'blob',
  })
}
