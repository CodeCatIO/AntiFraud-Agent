<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Fold, Expand, ArrowDown, UserFilled } from '@element-plus/icons-vue'
import { useAppStore } from '@/store/app'
import { useUserStore } from '@/store/user'
import { logout as logoutApi } from '@/api/user'
import Breadcrumb from '@/components/Breadcrumb.vue'

defineEmits(['toggle-sidebar'])

const router = useRouter()
const appStore = useAppStore()
const userStore = useUserStore()

const displayName = computed(
  () => userStore.userInfo?.nickname || userStore.userInfo?.username || '用户'
)

async function handleCommand(command) {
  if (command === 'profile') {
    router.push('/profile')
    return
  }
  if (command === 'password') {
    router.push('/password')
    return
  }
  if (command === 'logout') {
    try {
      await ElMessageBox.confirm('确定退出登录吗？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      })
    } catch {
      return
    }
    try {
      await logoutApi()
    } catch {
      // 即使接口失败也继续清理本地状态
    }
    userStore.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
  }
}
</script>

<template>
  <div class="header">
    <div class="header-left">
      <button type="button" class="collapse-btn" aria-label="切换侧边栏" @click="$emit('toggle-sidebar')"><el-icon :size="20">
        <Fold v-if="!appStore.isCollapse" />
        <Expand v-else />
      </el-icon></button>
      <Breadcrumb />
    </div>

    <div class="header-right">
      <el-dropdown trigger="click" @command="handleCommand">
        <span class="user-info">
          <el-avatar :size="32" :src="userStore.userInfo?.avatar">
            <el-icon :size="18"><UserFilled /></el-icon>
          </el-avatar>
          <span class="username">{{ displayName }}</span>
          <el-icon><ArrowDown /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">个人信息</el-dropdown-item>
            <el-dropdown-item command="password">修改密码</el-dropdown-item>
            <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;

  .collapse-btn {
    cursor: pointer;
    color: #536e7d;
    border: 0;
    background: rgba(255, 255, 255, .4);
    width: 34px;
    height: 34px;
    border-radius: 10px;
    transition: background-color .2s ease, box-shadow .2s ease;
    display: grid;
    place-items: center;

    &:hover {
      color: #167b81;
      background: rgba(255, 255, 255, .85);
      box-shadow: 0 5px 16px rgba(26, 103, 113, .09);
    }
  }
}

.header-right {
  .user-info {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    color: #264658;
    outline: none;
    padding: 4px 8px 4px 4px;
    border: 1px solid rgba(255, 255, 255, .7);
    border-radius: 24px;
    background: rgba(255, 255, 255, .45);
    transition: background-color .2s ease;
    &:hover { background: rgba(255, 255, 255, .85); }
    &:focus-visible { outline: 2px solid #167b81; outline-offset: 2px; }

    .username {
      font-size: 14px;
    }
  }
}
</style>
