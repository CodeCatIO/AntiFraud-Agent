import { defineStore } from 'pinia'
import { getToken, setToken, removeToken, getUser, setUser, clearAuth } from '@/utils/auth'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: getToken() || '',
    userInfo: getUser() || {
      username: '',
      nickname: '',
      avatar: '',
      roleId: null,
      role: '',
    },
  }),

  getters: {
    // 是否已登录
    isLoggedIn: (state) => !!state.token,

    // 是否为管理员
    isAdmin: (state) => state.userInfo?.roleId === 1,
    canReviewAgentRuns: (state) => ['ROLE_ADMIN', 'ROLE_MAINTENANCE'].includes(state.userInfo?.role),
  },

  actions: {
    // 登录：保存到 state 和 localStorage
    login(userData, token) {
      this.token = token
      this.userInfo = userData
      setToken(token)
      setUser(userData)
    },

    // 退出：清空 state 和 localStorage
    logout() {
      this.token = ''
      this.userInfo = {
        username: '',
        nickname: '',
        avatar: '',
        roleId: null,
        role: '',
      }
      clearAuth()
    },

    // 从 localStorage 恢复（页面刷新时用）
    loadFromStorage() {
      const token = getToken()
      const user = getUser()
      if (token) {
        this.token = token
      }
      if (user) {
        this.userInfo = user
      }
    },
  },
})
