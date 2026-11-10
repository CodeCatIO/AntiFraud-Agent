<script setup>
import { computed } from 'vue'

const props = defineProps({
  // 风险分数 0-100
  score: { type: Number, default: 0 },
  // 风险等级：高风险/中风险/低风险/安全
  level: { type: String, default: '安全' },
})

// 等级 → 进度条颜色
const levelColor = computed(
  () =>
    ({
      高风险: '#f56c6c',
      中风险: '#e6a23c',
      低风险: '#909399',
      安全: '#67c23a',
    })[props.level] || '#909399'
)

// 分数限制在 0-100
const percentage = computed(() => Math.min(100, Math.max(0, props.score)))
</script>

<template>
  <div class="risk-progress">
    <el-progress
      :percentage="percentage"
      :color="levelColor"
      :stroke-width="18"
      :text-inside="true"
    />
    <span class="score-text" :style="{ color: levelColor }">{{ score }} 分</span>
  </div>
</template>

<style scoped lang="scss">
.risk-progress {
  display: flex;
  align-items: center;
  gap: 12px;

  .el-progress {
    flex: 1;
  }

  .score-text {
    flex-shrink: 0;
    font-size: 14px;
    font-weight: 700;
  }
}
</style>
