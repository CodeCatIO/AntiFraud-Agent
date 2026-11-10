<script setup>
defineProps({
  icon: { type: [Object, Function], required: true },
  title: { type: String, required: true },
  description: { type: String, required: true },
})
</script>

<template>
  <div class="empty-state" role="status">
    <span class="empty-icon" aria-hidden="true"><el-icon><component :is="icon" /></el-icon></span>
    <strong>{{ title }}</strong>
    <p>{{ description }}</p>
  </div>
</template>

<style scoped lang="scss">
.empty-state { min-height: 190px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; padding: 24px; text-align: center; }
.empty-icon { width: 52px; height: 52px; display: grid; place-items: center; margin-bottom: 4px; border: 1px solid rgba(255, 255, 255, .88); border-radius: 16px; background: linear-gradient(140deg, rgba(220, 245, 244, .94), rgba(255, 255, 255, .52)); box-shadow: 0 9px 23px rgba(29, 111, 121, .09), inset 0 1px rgba(255, 255, 255, .9); color: #147883; font-size: 25px; }
strong { color: #25485b; font-size: 15px; }
p { max-width: 32ch; color: #637d89; font-size: 13px; line-height: 1.65; }
</style>
