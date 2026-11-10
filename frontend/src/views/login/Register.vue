<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { register } from '@/api/user'

const router = useRouter()

const formRef = ref(null)
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
  confirmPassword: '',
})

// 确认密码自定义验证器
function validateConfirmPassword(rule, value, callback) {
  if (value === '') {
    callback(new Error('请再次输入密码'))
  } else if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度为 3-20 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 20, message: '密码长度为 6-20 个字符', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

// 去登录
function goLogin() {
  router.push('/login')
}

async function handleRegister() {
  // 按钮点击必打日志
  console.log('注册按钮点击了，即将跳转登录页')

  // 表单验证（回调形式，失败不抛异常、不阻断）
  if (formRef.value) {
    let valid = true
    formRef.value.validate((isValid) => {
      valid = isValid
    })
    if (!valid) return
  }

  loading.value = true

  try {
    // 调用真实注册接口 POST /user/register
    await register({
      username: form.username,
      password: form.password,
    })

    ElMessage.success('注册成功，请登录')
    router.push('/login')
  } catch (e) {
    // 失败提示由响应拦截器统一弹出，这里只负责复位
    console.error('注册流程异常：', e)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="register-page">
    <el-card class="register-card" shadow="always">
      <div class="register-header">
        <h2 class="register-title">AI反诈骗检测系统</h2>
        <p class="register-subtitle">创建新账号</p>
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
          />
        </el-form-item>

        <el-form-item prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="请再次输入密码"
            :prefix-icon="Lock"
            show-password
            @keyup.enter="handleRegister"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            class="register-btn"
            :loading="loading"
            @click="handleRegister"
          >
            注 册
          </el-button>
        </el-form-item>
      </el-form>

      <div class="register-footer">
        已有账号？
        <button type="button" class="login-link" @click="goLogin">去登录</button>
      </div>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.register-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100dvh;
  padding: 24px;
  background: radial-gradient(ellipse 42% 36% at 75% 15%, rgba(153, 222, 222, .45), transparent 80%), radial-gradient(ellipse 40% 35% at 15% 82%, rgba(175, 206, 237, .4), transparent 80%), #edf5f7;
}

.register-card {
  width: min(440px, 100%);
  padding: 22px 20px 4px;
}

.register-header {
  text-align: center;
  margin-bottom: 24px;

  .register-title {
    font-size: 22px;
    font-weight: 600;
    color: #17384b;
  }

  .register-subtitle {
    margin-top: 8px;
    font-size: 13px;
    color: #627687;
  }
}

.register-btn {
  width: 100%;
}

.register-footer {
  text-align: center;
  padding-bottom: 16px;
  font-size: 14px;
  color: #627687;

  .login-link {
    border: 0;
    background: transparent;
    color: #167b81;
    font: inherit;
    font-weight: 600;
    cursor: pointer;

    &:hover {
      text-decoration: underline;
    }
  }
}
</style>
