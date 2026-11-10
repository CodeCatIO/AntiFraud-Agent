<script setup>
import { reactive } from 'vue'

const props = defineProps({
  round: { type: Number, default: 1 },
  questions: { type: Array, default: () => [] },
  busy: Boolean,
})
const emit = defineEmits(['submit'])
const answers = reactive({})

function submit() {
  const payload = {}
  for (const item of props.questions) {
    const value = answers[item.field]?.trim()
    if (value) payload[item.field] = value
  }
  if (Object.keys(payload).length) emit('submit', { round: props.round, answers: payload })
}
</script>

<template>
  <section class="supplement-panel">
    <header><div><span>MORE CONTEXT NEEDED</span><h2>补充线索信息</h2></div><el-tag effect="plain">第 {{ round }} 轮</el-tag></header>
    <p class="intro">只补充本次确实掌握的信息；不确定时可如实填写“不清楚”。</p>
    <el-form label-position="top" @submit.prevent="submit">
      <el-form-item v-for="item in questions" :key="item.field" :label="item.question">
        <el-input v-model="answers[item.field]" maxlength="500" show-word-limit placeholder="填写已知信息或说明不清楚" />
      </el-form-item>
      <el-button type="primary" :loading="busy" :disabled="!questions.length" @click="submit">提交补充并继续</el-button>
    </el-form>
  </section>
</template>

<style scoped lang="scss">
.supplement-panel { padding: 22px 24px; border: 1px solid #d8eae6; border-left: 4px solid #26877e; border-radius: 14px; background: #f5fbf8; }
header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; span { color: #24857d; font-size: 10px; font-weight: 700; letter-spacing: .12em; } h2 { margin: 4px 0 0; color: #214650; font-size: 17px; } }
.intro { margin: 10px 0 18px; color: #6b7f81; font-size: 12px; line-height: 1.6; }
.supplement-panel :deep(.el-form-item__label) { color: #365960; font-size: 13px; font-weight: 600; }
.supplement-panel .el-button { margin-top: 4px; }
@media (max-width: 520px) { .supplement-panel { padding: 18px; } .supplement-panel .el-button { width: 100%; } }
</style>
