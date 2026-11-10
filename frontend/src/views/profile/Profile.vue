<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UserFilled } from '@element-plus/icons-vue'
import { useUserStore } from '@/store/user'

const userStore = useUserStore()

const loading = ref(false)

// 可编辑的表单数据（从 store 初始化）
const form = reactive({
  username: '',
  nickname: '',
  email: '',
  phone: '',
})

// 操作日志（Mock 占位，接口通了以后删除）
const logs = ref([
  { id: 1, type: '检测', description: '文本诈骗检测', ip: '192.168.1.100', cost: 1250, time: '2026-05-07 10:23:45' },
  { id: 2, type: '登录', description: '用户登录', ip: '192.168.1.100', cost: 120, time: '2026-05-07 09:30:12' },
  { id: 3, type: '存证', description: '区块链存证', ip: '192.168.1.100', cost: 2100, time: '2026-05-06 14:32:10' },
  { id: 4, type: '下载', description: '下载检测报告', ip: '192.168.1.100', cost: 320, time: '2026-05-05 16:48:02' },
  { id: 5, type: '检测', description: '语音诈骗检测', ip: '192.168.1.102', cost: 3400, time: '2026-05-05 09:12:33' },
])

// 从 store 恢复用户信息
function initForm() {
  const info = userStore.userInfo || {}
  form.username = info.username || ''
  form.nickname = info.nickname || ''
  form.email = info.email || ''
  form.phone = info.phone || ''
}

async function handleSave() {
  if (!form.nickname.trim()) {
    ElMessage.warning('昵称不能为空')
    return
  }
  loading.value = true
  try {
    // 接口未通前用 Mock 占位，接口通了以后替换为：
    // await updateProfile({ nickname: form.nickname, email: form.email, phone: form.phone })
    await new Promise((resolve) => setTimeout(resolve, 600))

    // 同步更新到 store 和 localStorage
    userStore.userInfo = { ...userStore.userInfo, ...form }
    ElMessage.success('保存成功')
  } catch (e) {
    // 错误已由拦截器统一提示
  } finally {
    loading.value = false
  }
}

async function loadLogs() {
  // 接口未通前用 Mock 占位，接口通了以后替换为：
  // const res = await getMyLogs({ pageNum: 1, pageSize: 10 })
  // logs.value = res.list || []
}

onMounted(() => {
  initForm()
  loadLogs()
})
</script>

<template>
  <div class="profile">
    <el-row :gutter="16">
      <!-- 左：用户信息卡片 -->
      <el-col :xs="24" :md="10">
        <el-card shadow="hover">
          <template #header>
            <span class="card-title">个人信息</span>
          </template>

          <div class="avatar-block">
            <el-avatar :size="80" :src="userStore.userInfo?.avatar">
              <el-icon :size="40"><UserFilled /></el-icon>
            </el-avatar>
            <div class="user-meta">
              <div class="username">{{ form.username || '未登录' }}</div>
              <el-tag v-if="userStore.isAdmin" type="danger" size="small">管理员</el-tag>
              <el-tag v-else type="info" size="small">普通用户</el-tag>
            </div>
          </div>

          <el-form label-width="80px" @submit.prevent>
            <el-form-item label="用户名">
              <el-input v-model="form.username" disabled />
            </el-form-item>
            <el-form-item label="昵称">
              <el-input v-model="form.nickname" placeholder="请输入昵称" maxlength="20" />
            </el-form-item>
            <el-form-item label="邮箱">
              <el-input v-model="form.email" placeholder="请输入邮箱" />
            </el-form-item>
            <el-form-item label="手机号">
              <el-input v-model="form.phone" placeholder="请输入手机号" maxlength="11" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="loading" @click="handleSave">保存</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 右：操作日志 -->
      <el-col :xs="24" :md="14">
        <el-card shadow="hover">
          <template #header>
            <span class="card-title">最近操作日志</span>
          </template>

          <el-table :data="logs" stripe border>
            <el-table-column prop="type" label="操作类型" width="90" align="center">
              <template #default="{ row }">
                <el-tag size="small">{{ row.type }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="操作描述" min-width="130" />
            <el-table-column prop="ip" label="IP地址" width="130" />
            <el-table-column label="耗时(ms)" width="90" align="center">
              <template #default="{ row }">{{ row.cost }}</template>
            </el-table-column>
            <el-table-column prop="time" label="操作时间" width="165" align="center" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.profile {
  .card-title {
    font-size: 15px;
    font-weight: 600;
    color: #303133;
  }

  .avatar-block {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 24px;
    padding: 8px 0 16px;
    border-bottom: 1px solid #e6e8eb;

    .user-meta {
      .username {
        font-size: 18px;
        font-weight: 600;
        color: #303133;
        margin-bottom: 6px;
      }
    }
  }
}
</style>
