<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useAppStore } from '@/store/app'
import Aside from './Aside.vue'
import Header from './Header.vue'

const appStore = useAppStore()

const isMobile = ref(window.innerWidth < 768)
const drawerVisible = ref(false)

function handleResize() {
  isMobile.value = window.innerWidth < 768
  if (!isMobile.value) drawerVisible.value = false
}

// 折叠按钮：桌面端切换折叠，移动端打开抽屉
function handleToggleSidebar() {
  if (isMobile.value) {
    drawerVisible.value = true
  } else {
    appStore.toggleCollapse()
  }
}

onMounted(() => window.addEventListener('resize', handleResize))
onUnmounted(() => window.removeEventListener('resize', handleResize))
</script>

<template>
  <el-container class="manage">
    <!-- 桌面端侧边栏（可折叠） -->
    <el-aside v-if="!isMobile" class="manage-aside" :width="appStore.isCollapse ? '64px' : '220px'">
      <Aside />
    </el-aside>

    <!-- 移动端抽屉侧边栏 -->
    <el-drawer
      v-model="drawerVisible"
      class="manage-drawer"
      direction="ltr"
      :size="220"
      :with-header="false"
    >
      <Aside mobile @select="drawerVisible = false" />
    </el-drawer>

    <el-container class="manage-body">
      <el-header class="manage-header">
        <Header @toggle-sidebar="handleToggleSidebar" />
      </el-header>
      <el-main class="manage-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.manage {
  height: 100%;
  background:
    radial-gradient(ellipse 48% 42% at 73% 7%, rgba(155, 221, 221, .38), transparent 78%),
    radial-gradient(ellipse 42% 38% at 22% 82%, rgba(179, 210, 239, .34), transparent 78%),
    linear-gradient(145deg, #eef5f7 0%, #e9f1f4 48%, #f4f8f8 100%);
}

.manage-aside {
  border-right: 1px solid rgba(255, 255, 255, .78);
  transition: width .32s ease;
  overflow-x: hidden;
  background: rgba(246, 252, 252, .67);
  backdrop-filter: blur(22px) saturate(1.25);
  -webkit-backdrop-filter: blur(22px) saturate(1.25);
  box-shadow: 8px 0 32px rgba(27, 82, 100, .055), inset -1px 0 rgba(117, 163, 178, .13);
}

.manage-header {
  height: $header-height;
  padding: 0 24px;
  border-bottom: 1px solid rgba(255, 255, 255, .85);
  background: rgba(250, 254, 254, .63);
  backdrop-filter: blur(20px) saturate(1.2);
  -webkit-backdrop-filter: blur(20px) saturate(1.2);
  box-shadow: 0 6px 24px rgba(27, 82, 100, .045);
  position: relative;
  z-index: 2;
}

.manage-main {
  background: transparent;
  padding: 28px;
}
@media (max-width: 768px) {
  .manage-header { padding: 0 16px; }
  .manage-main { padding: 18px 14px; }
}
</style>

<style lang="scss">
// 抽屉（teleport 到 body，需要全局样式）
.manage-drawer .el-drawer__body {
  padding: 0;
  background: linear-gradient(155deg, rgba(250, 254, 254, .94), rgba(232, 246, 248, .96));
}

@supports not (backdrop-filter: blur(1px)) {
  .manage-aside, .manage-header { background: #f5fbfb; }
}

@media (prefers-reduced-transparency: reduce) {
  .manage-aside, .manage-header { background: #f5fbfb; backdrop-filter: none; -webkit-backdrop-filter: none; }
}
</style>
