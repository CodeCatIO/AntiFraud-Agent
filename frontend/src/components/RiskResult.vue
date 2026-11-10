<script setup>
import { computed } from 'vue'

const props = defineProps({
  level: { type: String, default: '' },
  score: { type: Number, default: null },
  confidence: { type: Number, default: null },
})

const riskType = computed(() => ({
  高风险: 'danger', 中风险: 'warning', 低风险: 'info', 安全: 'success',
})[props.level] || 'info')
const scoreValue = computed(() => Number.isFinite(props.score) ? Math.max(0, Math.min(100, props.score)) : 0)
const advice = computed(() => {
  if (props.level === '高风险' || props.level === '中风险') {
    return '请暂停转账、提供验证码或打开可疑链接；通过官方渠道核实对方身份。'
  }
  return '检测结果仅供参考。如涉及资金或个人信息，请继续通过官方渠道核实。'
})
</script>

<template>
  <section class="risk-result" aria-live="polite">
    <div class="result-top">
      <div><h2>检测结果</h2><p>依据本次提交的内容生成</p></div>
      <el-tag :type="riskType" size="large" effect="light">{{ level || '待评估' }}</el-tag>
    </div>
    <div class="score-line"><span>风险分数</span><strong>{{ score ?? '—' }}<small v-if="score !== null"> / 100</small></strong></div>
    <el-progress v-if="score !== null" :percentage="scoreValue" :show-text="false" :stroke-width="8" :color="level === '高风险' ? '#c54848' : level === '中风险' ? '#b36a17' : '#167b81'" />
    <p v-if="confidence !== null && Number.isFinite(confidence)" class="confidence">模型返回的置信度：{{ (confidence * 100).toFixed(1) }}%</p>
    <div class="evidence"><h3>检测依据</h3><slot><p>当前结果没有提供进一步的分析依据。</p></slot></div>
    <div class="advice"><h3>建议下一步</h3><p>{{ advice }}</p></div>
    <p class="disclaimer">AI 检测不能替代人工核实，也不能单独作为诈骗或真伪的最终判定。</p>
  </section>
</template>

<style scoped lang="scss">
.risk-result { color: #20394c; }
.result-top { display: flex; justify-content: space-between; gap: 14px; align-items: start; margin-bottom: 25px; h2 { font-size: 18px; } p { margin-top: 6px; color: #6b7c88; font-size: 13px; } }
.score-line { display: flex; justify-content: space-between; align-items: end; margin-bottom: 10px; color: #617487; font-size: 13px; strong { color: #19384a; font-size: 30px; line-height: 1; font-variant-numeric: tabular-nums; } small { color: #697c89; font-size: 13px; font-weight: 400; } }
.confidence { margin-top: 12px; color: #627687; font-size: 13px; }
.evidence { margin-top: 28px; padding-top: 22px; border-top: 1px solid #e6edef; }
.evidence h3, .advice h3 { font-size: 14px; color: #19384a; margin-bottom: 10px; }
.evidence :deep(p) { color: #405b6c; font-size: 14px; line-height: 1.75; white-space: pre-wrap; overflow-wrap: anywhere; }
.advice { margin-top: 22px; padding: 17px 18px; border-radius: 9px; background: #eaf5f3; p { color: #235963; font-size: 14px; line-height: 1.7; } }
.disclaimer { margin-top: 18px; color: #6a7e8a; font-size: 12px; line-height: 1.6; }
</style>
