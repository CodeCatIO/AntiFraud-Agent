<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/store/user'
import { login } from '@/api/user'

const router = useRouter()
const userStore = useUserStore()

const formRef = ref(null)
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度为 3-20 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 20, message: '密码长度为 6-20 个字符', trigger: 'blur' },
  ],
}

// 立即注册
function goRegister() {
  router.push('/register')
}

async function handleLogin() {
  if (formRef.value) {
    try {
      await formRef.value.validate()
    } catch {
      return
    }
  }

  loading.value = true

  try {
    // 调用真实登录接口 POST /user/login
    const res = await login({
      username: form.username,
      password: form.password,
    })
    // res 为后端返回的 UserDTO（响应拦截器已解包 data）
    const token = res?.token
    if (!token) {
      throw new Error('登录成功但未返回 token')
    }

    userStore.login(
      {
        username: res.username || form.username,
        nickname: res.nickname || res.username || form.username,
        avatar: res.avatarUrl || '',
        roleId: res.roleid ?? null,
        role: res.role || '',
      },
      token
    )

    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch (e) {
    // 失败提示由响应拦截器统一弹出，这里只负责复位
    console.error('登录流程异常：', e)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-intro">
      <div class="login-brand"><span class="brand-shield"><i /></span><span>识诈</span></div>
      <div class="intro-copy">
        <h1>让每一次判断<br />都有依据。</h1>
        <p>汇集文本、语音与图片检测线索，帮助你更清晰地识别风险、留存记录。</p>
      </div>
      <div class="intro-foot">多模态 AI 风险检测平台</div>
    </div>
    <div class="login-form-area"><el-card class="login-card" shadow="never">
      <div class="login-header">
        <h2 class="login-title">欢迎回来</h2>
        <p class="login-subtitle">登录后继续查看检测记录与风险分析</p>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" size="large">
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            :prefix-icon="User"
            clearable
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            class="login-btn"
            :loading="loading"
            @click="handleLogin"
          >
            登录工作台
          </el-button>
        </el-form-item>
      </el-form>

      <div class="login-footer">
        还没有账号？
        <button type="button" class="register-link" @click="goRegister">立即注册</button>
      </div>
    </el-card></div>
  </div>
</template>

<style scoped lang="scss">
.login-page {
  min-height: 100%;
  display: grid;
  grid-template-columns: minmax(360px, 48%) 1fr;
  background: #f5f8f8;
}
.login-intro { padding: 50px clamp(34px, 6vw, 100px); display: flex; flex-direction: column; justify-content: space-between; background: #173b4f; color: #fff; }
.login-brand { display: flex; align-items: center; gap: 12px; font-size: 22px; font-weight: 700; letter-spacing: .08em; }
.brand-shield { width: 36px; height: 40px; display: grid; place-items: center; background: #65c8bf; clip-path: polygon(50% 0, 94% 15%, 89% 69%, 50% 100%, 11% 69%, 6% 15%); i { width: 12px; height: 18px; border-right: 3px solid #123b46; border-bottom: 3px solid #123b46; transform: translateY(-3px) rotate(42deg); } }
.intro-copy { max-width: 520px; h1 { font-size: clamp(38px, 4vw, 58px); line-height: 1.23; letter-spacing: -.03em; } p { margin-top: 27px; font-size: 17px; line-height: 1.8; color: #c8dcdf; } }
.intro-foot { color: #bed4d8; font-size: 13px; letter-spacing: .04em; }
.login-form-area { display: grid; place-items: center; padding: 32px; background: radial-gradient(ellipse 55% 40% at 76% 18%, rgba(156, 221, 221, .39), transparent 82%), radial-gradient(ellipse 46% 39% at 18% 83%, rgba(177, 207, 235, .35), transparent 82%), #edf5f7; }
.login-card { width: min(440px, 100%); padding: 22px; border: 1px solid rgba(255, 255, 255, .88); background: rgba(255, 255, 255, .75); box-shadow: var(--surface-glass-shadow); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); }
.login-card :deep(.el-card__body) { padding: 18px 14px 4px; }
.login-card :deep(.el-form-item) { margin-bottom: 22px; }
.login-card :deep(.el-input__wrapper) { min-height: 45px; }
.login-card :deep(.el-button) { min-height: 44px; }
.login-header { margin-bottom: 32px; text-align: left; }
.login-title { color: #17384b; font-size: 28px; }
.login-subtitle { margin-top: 9px; font-size: 14px; color: #617687; }
.login-btn { width: 100%; }
.login-footer { text-align: center; padding: 6px 0 13px; font-size: 14px; color: #627687; }
.register-link { background: transparent; border: 0; color: #167b81; font: inherit; font-weight: 600; cursor: pointer; &:hover { text-decoration: underline; } }
@media (max-width: 800px) {
  .login-page { grid-template-columns: 1fr; }
  .login-intro { min-height: 240px; padding: 26px; gap: 22px; }
  .intro-copy h1 { font-size: 30px; }
  .intro-copy p { margin-top: 10px; font-size: 14px; }
  .intro-foot { display: none; }
  .login-form-area { padding: 28px 18px; align-items: start; }
  .login-card { padding: 8px; }
}
</style>
