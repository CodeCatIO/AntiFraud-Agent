<script setup>
import { computed, markRaw } from 'vue'
import { useRoute } from 'vue-router'
import {
  Odometer,
  Monitor,
  List,
  Link,
  Stamp,
  Setting,
  Operation,
} from '@element-plus/icons-vue'
import { useAppStore } from '@/store/app'
import { useUserStore } from '@/store/user'

defineEmits(['select'])
defineProps({ mobile: Boolean })

const route = useRoute()
const appStore = useAppStore()
const userStore = useUserStore()

// Mock 菜单数据（与路由 meta 的 title/icon 对应）
const menus = computed(() => {
  const list = [
    { path: '/dashboard', title: '仪表盘', icon: markRaw(Odometer) },
    { path: '/agent', title: '线索研判', icon: markRaw(Operation) },
    {
      title: '多模态检测',
      icon: markRaw(Monitor),
      children: [
        { path: '/detect/text', title: '文本检测' },
        { path: '/detect/voice', title: '语音检测' },
        { path: '/detect/image', title: '图片检测' },
      ],
    },
    { path: '/records', title: '检测记录', icon: markRaw(List) },
    { path: '/blockchain', title: '区块链存证', icon: markRaw(Link) },
    { path: '/watermark', title: '水印工具', icon: markRaw(Stamp) },
  ]

  // 系统管理仅管理员可见
  if (userStore.isAdmin) {
    list.push({
      title: '系统管理',
      icon: markRaw(Setting),
      children: [
        { path: '/system/user', title: '用户管理' },
        { path: '/system/role', title: '角色管理' },
        { path: '/system/menu', title: '菜单管理' },
        { path: '/system/log', title: '操作日志' },
      ],
    })
  }

  return list
})
</script>

<template>
  <div class="aside-inner">
  <div class="brand" :class="{ compact: appStore.isCollapse && !mobile }">
    <span class="brand-mark"><span /></span>
    <span class="brand-copy" :aria-hidden="appStore.isCollapse && !mobile"><strong>识诈</strong><small>AI 风险检测平台</small></span>
  </div>
  <el-menu
    class="aside-menu"
    :default-active="route.path"
    :collapse="appStore.isCollapse && !mobile"
    :collapse-transition="false"
    unique-opened
    router
    @select="$emit('select')"
  >
    <template v-for="item in menus" :key="item.path || item.title">
      <!-- 二级菜单 -->
      <el-sub-menu v-if="item.children" :index="item.title" :aria-label="item.title">
        <template #title>
          <el-icon><component :is="item.icon" /></el-icon>
          <span class="menu-label" :aria-hidden="appStore.isCollapse && !mobile">{{ item.title }}</span>
        </template>
        <el-menu-item v-for="child in item.children" :key="child.path" :index="child.path">
          {{ child.title }}
        </el-menu-item>
      </el-sub-menu>

      <!-- 一级菜单 -->
      <el-menu-item v-else :index="item.path" :aria-label="item.title" :title="appStore.isCollapse && !mobile ? item.title : undefined">
        <el-icon><component :is="item.icon" /></el-icon>
        <span class="menu-label" :aria-hidden="appStore.isCollapse && !mobile">{{ item.title }}</span>
      </el-menu-item>
    </template>
  </el-menu>
  </div>
</template>

<style scoped lang="scss">
.aside-inner { height: 100%; display: flex; flex-direction: column; }
.brand { height: 72px; display: flex; align-items: center; gap: 12px; padding: 0 22px; flex: none; transition: padding .32s ease; }
.brand.compact { padding: 0 15px; }
.brand-mark { width: 34px; height: 38px; flex: none; display: grid; place-items: center; background: linear-gradient(150deg, #2aa8a9, #11636f 76%); box-shadow: 0 8px 18px rgba(18, 100, 112, .2); clip-path: polygon(50% 0, 94% 15%, 89% 69%, 50% 100%, 11% 69%, 6% 15%); span { width: 12px; height: 18px; border-right: 3px solid #fff; border-bottom: 3px solid #fff; transform: translateY(-3px) rotate(42deg); } }
.brand-copy { display: flex; flex-direction: column; flex: none; width: 126px; white-space: nowrap; color: #17384b; opacity: 1; transform: translateX(0); transition: opacity .2s ease .11s, transform .28s ease .08s; strong { font-size: 19px; letter-spacing: .08em; } small { margin-top: 2px; font-size: 11px; color: #6a7e8b; letter-spacing: .04em; } }
.brand.compact .brand-copy { opacity: 0; transform: translateX(-8px); transition-delay: 0s; pointer-events: none; }
.aside-menu {
  flex: 1;
  border-right: none;
  padding: 4px 10px 12px;
  background: transparent;
  --el-menu-bg-color: transparent;
  --el-menu-hover-bg-color: rgba(255, 255, 255, .62);
  --el-menu-active-color: #096c72;
  :deep(.el-menu-item), :deep(.el-sub-menu__title) { height: 46px; line-height: 46px; border-radius: 11px; margin: 2px 0; transition: background-color .2s ease, box-shadow .2s ease; }
  :deep(.menu-label) { display: inline-block; flex: none; white-space: nowrap; opacity: 1; transform: translateX(0); transition: opacity .2s ease .11s, transform .28s ease .08s; }
  &.el-menu--collapse :deep(.menu-label) { width: auto; height: auto; overflow: visible; visibility: visible; opacity: 0; transform: translateX(-8px); transition-delay: 0s; pointer-events: none; }
  :deep(.el-sub-menu .el-menu-item) { height: 40px; line-height: 40px; }
  :deep(.el-menu-item.is-active) { background: linear-gradient(110deg, rgba(255, 255, 255, .88), rgba(224, 247, 245, .72)); border: 1px solid rgba(255, 255, 255, .88); box-shadow: 0 7px 20px rgba(26, 103, 113, .1), inset 0 1px rgba(255, 255, 255, .9); font-weight: 600; }
  :deep(.el-sub-menu .el-menu) { background: transparent; }
}
@media (prefers-reduced-motion: reduce) {
  .brand, .brand-copy, .aside-menu :deep(.menu-label) { transition: none; }
}
</style>
