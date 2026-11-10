import request from '@/utils/request'

// 数据集分类标签分布（三模态，供可视化）
export function getDatasetLabels() {
  return request.get('/dataset/labels')
}
