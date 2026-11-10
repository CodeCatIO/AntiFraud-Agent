import request from '@/utils/request'

// 构建用户菜单
export function buildMenu() {
  return request.get('/menu/build')
}
