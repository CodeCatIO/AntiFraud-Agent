const TOKEN_KEY = 'token'
const USER_KEY = 'user'

// token 操作
export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function removeToken() {
  localStorage.removeItem(TOKEN_KEY)
}

// 用户信息操作
export function getUser() {
  const user = localStorage.getItem(USER_KEY)
  try {
    return user ? JSON.parse(user) : null
  } catch (e) {
    return null
  }
}

export function setUser(user) {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function removeUser() {
  localStorage.removeItem(USER_KEY)
}

// 清除所有认证信息
export function clearAuth() {
  removeToken()
  removeUser()
}
