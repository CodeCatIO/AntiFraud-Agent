import request from '@/utils/request'

// 用户登录
export function login(data) {
  return request.post('/user/login', data)
}

// 用户注册
export function register(data) {
  return request.post('/user/register', data)
}

// 退出登录
export function logout() {
  return request.post('/user/logout')
}

// 根据用户名查询用户信息
export function getUserByUsername(username) {
  return request.get(`/user/username/${username}`)
}

// 修改密码
export function updatePassword(data) {
  return request.put('/user/password', data)
}
