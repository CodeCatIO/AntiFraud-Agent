<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Lock } from '@element-plus/icons-vue'
import { updatePassword } from '@/api/user'
import { useUserStore } from '@/store/user'

const router = useRouter()
const userStore = useUserStore()

const formRef = ref(null)
const loading = ref(false)

const form = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

// 确认新密码自定义验证器
function validateConfirmPassword(rule, value, callback) {
  if (value === '') {
    callback(new Error('请再次输入新密码'))
  } else if (value !== form.newPassword) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  oldPassword: [{ required: true, message: '请输入旧密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 20, message: '新密码长度为 6-20 个字符', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

async function handleSubmit() {
  await formRef.value.validate()
  loading.value = true
  try {
    // 接口未通前用 Mock 占位，接口通了以后替换为：
    // await updatePassword({
    //   oldPassword: form.oldPassword,
    //   newPassword: form.newPassword,
    // })
    await new Promise((resolve) => setTimeout(resolve, 800))

    ElMessage.success('密码修改成功，请重新登录')
    // 清除登录态并跳转登录页
    userStore.logout()
    router.push('/login')
  } catch (e) {
    // 错误已由拦截器统一提示
  } finally {
    loading.value = false
  }
}

function handleReset() {
  formRef.value?.resetFields()
}
</script>

<template>
  <div class="password-page">
    <el-row justify="center">
      <el-col :xs="24" :sm="16" :md="10">
        <el-card shadow="hover">
          <template #header>
            <span class="card-title">修改密码</span>
          </template>

          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-width="90px"
            size="large"
            @submit.prevent
          >
            <el-form-item label="旧密码" prop="oldPassword">
              <el-input
                v-model="form.oldPassword"
                type="password"
                placeholder="请输入旧密码"
                :prefix-icon="Lock"
                show-password
              />
            </el-form-item>

            <el-form-item label="新密码" prop="newPassword">
              <el-input
                v-model="form.newPassword"
                type="password"
                placeholder="请输入新密码（6-20字符）"
                :prefix-icon="Lock"
                show-password
              />
            </el-form-item>

            <el-form-item label="确认密码" prop="confirmPassword">
              <el-input
                v-model="form.confirmPassword"
                type="password"
                placeholder="请再次输入新密码"
                :prefix-icon="Lock"
                show-password
                @keyup.enter="handleSubmit"
              />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" :loading="loading" @click="handleSubmit">确认修改</el-button>
              <el-button @click="handleReset">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.password-page {
  .card-title {
    font-size: 15px;
    font-weight: 600;
    color: #303133;
  }
}
</style>
