import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { getToken, clearAuth } from './auth'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30000,
})

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    const token = getToken()
    if (token) {
      // 后端 JwtInterceptor 读取 token 头
      config.headers.token = token
      // 同时附带标准 Authorization Bearer 头
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  (res) => {
    const code = res.data?.code
    if (code === '200') {
      return res.data.data
    }
    if (code === '401') {
      ElMessage.error('登录已过期')
      clearAuth()
      router.push('/login')
      return Promise.reject(new Error('登录已过期'))
    }
    if (code === '403') {
      ElMessage.error('无权限访问')
      return Promise.reject(new Error('无权限访问'))
    }
    if (code === '600') {
      ElMessage.error(res.data.msg || '业务异常')
      return Promise.reject(new Error(res.data.msg || '业务异常'))
    }
    ElMessage.error(res.data.msg || '请求失败')
    return Promise.reject(new Error(res.data.msg || '请求失败'))
  },
  (error) => {
    ElMessage.error(error.message)
    return Promise.reject(error)
  }
)

export default request
