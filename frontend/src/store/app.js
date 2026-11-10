import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', {
  state: () => ({
    isCollapse: false, // 侧边栏折叠状态
    currentPathName: '仪表盘', // 当前页面名
  }),

  actions: {
    // 切换侧边栏折叠状态
    toggleCollapse() {
      this.isCollapse = !this.isCollapse
    },

    // 设置当前页面名
    setCurrentPathName(name) {
      this.currentPathName = name
    },
  },
})
