<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Refresh } from '@element-plus/icons-vue'
import { detectText } from '@/api/detect'
import RiskResult from '@/components/RiskResult.vue'

const inputText = ref('')
const loading = ref(false)
const result = ref(null)

async function handleDetect() {
  if (!inputText.value.trim()) {
    ElMessage.warning('请输入待检测的文本内容')
    return
  }
  loading.value = true
  result.value = null
  try {
    const res = await detectText(inputText.value)
    const detail = res.detail || {}
    result.value = {
      score: res.riskScore,
      level: res.riskLevel,
      keywords: Array.isArray(detail.keywords) ? detail.keywords : [],
      analysis: detail.detail || detail.analysis || '',
    }
  } catch {
    // 请求拦截器已提示错误
  } finally {
    loading.value = false
  }
}

function handleClear() { inputText.value = ''; result.value = null }
</script>

<template>
  <div class="text-detect">
    <div class="page-heading"><h1>文本检测</h1><p>粘贴短信、聊天记录或通知内容，查看可疑线索与风险建议。</p></div>
    <div class="detect-grid" :class="{ 'has-result': result }">
      <section class="input-panel">
        <div class="section-heading"><h2>待检测内容</h2><p>请勿填写密码、验证码等敏感信息。</p></div>
        <el-input v-model="inputText" type="textarea" :rows="11" maxlength="2000" show-word-limit placeholder="在此粘贴需要核实的文字内容…" />
        <div class="actions">
          <el-button type="primary" :icon="Search" :loading="loading" @click="handleDetect">开始检测</el-button>
          <el-button :icon="Refresh" :disabled="loading || !inputText" @click="handleClear">清空内容</el-button>
        </div>
      </section>

      <section v-if="result" class="result-panel">
        <RiskResult :level="result.level" :score="result.score">
          <div v-if="result.keywords.length" class="keywords"><span v-for="word in result.keywords" :key="word">{{ word }}</span></div>
          <p v-if="result.analysis">{{ result.analysis }}</p>
          <p v-if="!result.keywords.length && !result.analysis">当前结果未提供具体线索，请结合实际情况核实。</p>
        </RiskResult>
      </section>
      <aside v-else class="guide-panel">
        <h2>提交前，请先确认</h2>
        <div class="guide-item"><strong>保留原文</strong><p>尽量完整粘贴消息，避免遗漏上下文。</p></div>
        <div class="guide-item"><strong>保护隐私</strong><p>不要提交身份证号、银行卡号、密码或验证码。</p></div>
        <div class="guide-item"><strong>独立核实</strong><p>涉及转账、领奖或账户异常时，请直接联系官方渠道。</p></div>
      </aside>
    </div>
  </div>
</template>

<style scoped lang="scss">
.text-detect { max-width: 1440px; margin: 0 auto; }
.page-heading { margin-bottom: 24px; h1 { font-size: 27px; color: #172e43; } p { margin-top: 7px; color: #647887; } }
.detect-grid { display: grid; grid-template-columns: minmax(0, 1.65fr) minmax(260px, .75fr); gap: 18px; align-items: start; }
.detect-grid.has-result { grid-template-columns: minmax(0, 1fr) minmax(340px, 1fr); }
.input-panel, .guide-panel, .result-panel { background: var(--surface-glass); border: 1px solid var(--surface-glass-border); border-radius: 18px; padding: 26px; box-shadow: var(--surface-glass-shadow); backdrop-filter: blur(16px) saturate(1.18); -webkit-backdrop-filter: blur(16px) saturate(1.18); }
.section-heading { margin-bottom: 20px; h2 { font-size: 18px; color: #19384a; } p { margin-top: 7px; color: #687c8a; font-size: 13px; } }
.input-panel :deep(.el-textarea__inner) { line-height: 1.75; padding: 15px; resize: vertical; }
.actions { display: flex; gap: 10px; margin-top: 20px; .el-button + .el-button { margin-left: 0; } }
.guide-panel { background: linear-gradient(145deg, rgba(227, 246, 244, .85), rgba(251, 255, 255, .58)); border-color: rgba(255, 255, 255, .9); h2 { font-size: 16px; color: #1a4453; margin-bottom: 16px; } }
.guide-item { padding: 15px 0; border-top: 1px solid #d5e6e5; strong { display: block; font-size: 14px; color: #245668; } p { margin-top: 5px; color: #516f7b; font-size: 13px; line-height: 1.65; } }
.keywords { display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 12px; span { padding: 5px 9px; background: #fbeceb; color: #9c3d3d; border-radius: 5px; font-size: 13px; } }
@media (max-width: 900px) { .detect-grid, .detect-grid.has-result { grid-template-columns: 1fr; } }
@media (max-width: 600px) { .page-heading h1 { font-size: 23px; }.input-panel, .guide-panel, .result-panel { padding: 18px; } }
@supports not (backdrop-filter: blur(1px)) {
  .input-panel, .result-panel { background: #fff; }
}
@media (prefers-reduced-transparency: reduce) {
  .input-panel, .result-panel { background: #fff; backdrop-filter: none; -webkit-backdrop-filter: none; }
}
</style>
