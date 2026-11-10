<script setup>
import { computed } from 'vue'

const props = defineProps({
  // 风险等级：高风险/中风险/低风险/安全
  level: { type: String, default: '安全' },
  // 标签尺寸：''/small/large
  size: { type: String, default: '' },
})

// 等级 → 标签类型
const levelTagType = computed(
  () =>
    ({
      高风险: 'danger',
      中风险: 'warning',
      低风险: 'info',
      安全: 'success',
    })[props.level] || 'info'
)
</script>

<template>
  <el-tag :type="levelTagType" :size="size">{{ level }}</el-tag>
</template>
