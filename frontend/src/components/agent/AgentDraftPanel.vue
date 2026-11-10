<script setup>
import { computed } from 'vue'

const props = defineProps({ draft: { type: Object, default: () => ({}) } })
const detection = computed(() => props.draft?.detection || {})
const citations = computed(() => Array.isArray(props.draft?.citations) ? props.draft.citations : [])
const facts = computed(() => Array.isArray(props.draft?.extractedFacts) ? props.draft.extractedFacts : [])

const riskType = computed(() => ({
  高风险: 'danger',
  中风险: 'warning',
  低风险: 'success',
  安全: 'success',
}[detection.value.riskLevel] || 'info'))

function displayField(item) {
  if (item && typeof item === 'object') return `${item.field || '事实'}：${item.value || ''}`
  return String(item)
}
</script>

<template>
  <section class="draft-panel panel">
    <header class="section-title"><div><span>REVIEW DRAFT</span><h2>研判草稿</h2></div><el-tag :type="detection.status === 'completed' ? riskType : 'info'" effect="light">{{ detection.status === 'completed' ? (detection.riskLevel || '检测完成') : '检测未完成' }}</el-tag></header>
    <p class="draft-summary">{{ draft.summary || '正在生成研判草稿…' }}</p>

    <div class="signal-row">
      <div><span>检测状态</span><strong>{{ detection.status || '等待中' }}</strong></div>
      <div><span>风险分数</span><strong>{{ detection.status === 'completed' && detection.riskScore != null ? detection.riskScore : '—' }}</strong></div>
      <div><span>引用来源</span><strong>{{ citations.length }}</strong></div>
    </div>
    <p v-if="detection.status !== 'completed'" class="boundary-note">检测失败或未返回分数时不显示风险等级；请以原始证据和其他核查结果为准。</p>

    <section v-if="facts.length" class="draft-section">
      <h3>提取事实</h3>
      <ul><li v-for="(fact, index) in facts" :key="index">{{ displayField(fact) }}</li></ul>
    </section>
    <section v-if="draft.suggestedChecks?.length" class="draft-section">
      <h3>建议核查</h3>
      <ul><li v-for="(check, index) in draft.suggestedChecks" :key="index">{{ check }}</li></ul>
    </section>
    <section v-if="draft.uncertaintyNotes?.length" class="draft-section uncertainty">
      <h3>不确定性</h3>
      <ul><li v-for="(note, index) in draft.uncertaintyNotes" :key="index">{{ note }}</li></ul>
    </section>
    <section v-if="citations.length" class="draft-section">
      <h3>知识依据 <small>以下为来源卡转述，不是原文引述</small></h3>
      <article v-for="(citation, index) in citations" :key="citation.chunkId" class="citation">
        <div class="citation-head">
          <span class="citation-index">{{ index + 1 }}</span>
          <div class="citation-meta">
            <strong>{{ citation.title || citation.documentId }}</strong>
            <span>{{ citation.publisher }} · {{ citation.publishedAt || '日期未记录' }} · {{ citation.locator || '来源卡' }}</span>
          </div>
          <el-tag size="small" effect="plain" type="warning">{{ citation.excerptType === 'paraphrase' ? '转述' : '摘录' }}</el-tag>
        </div>
        <p>{{ citation.content || citation.excerpt || citation.paraphrase || '' }}</p>
        <footer class="citation-foot">
          <span class="chunk-id">出处编号 {{ (citation.chunkId || '').slice(0, 12) || '未记录' }}</span>
          <a v-if="citation.sourceUrl" :href="citation.sourceUrl" target="_blank" rel="noopener noreferrer">打开原始来源 ↗</a>
        </footer>
      </article>
    </section>
    <el-empty v-if="!citations.length && draft.summary" description="没有命中可回查知识来源" :image-size="46" />
  </section>
</template>

<style scoped lang="scss">
.panel { border: 1px solid #dce9e8; border-radius: 16px; background: #fff; box-shadow: 0 14px 34px rgba(24, 63, 73, .055); }
.draft-panel { padding: 24px; }
.section-title { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px; span { color: #1a817c; font-size: 10px; font-weight: 700; letter-spacing: .12em; } h2 { margin: 4px 0 0; color: #19384a; font-size: 18px; } }
.draft-summary { margin: 0; color: #294957; line-height: 1.8; white-space: pre-wrap; overflow-wrap: anywhere; }
.signal-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 20px 0 0; padding: 15px 0; border-top: 1px solid #e7efee; border-bottom: 1px solid #e7efee; div { display: flex; flex-direction: column; gap: 6px; } span { color: #7c8e95; font-size: 11px; } strong { color: #284a58; font-size: 13px; } }
.boundary-note { margin: 12px 0 0; color: #826b43; font-size: 12px; line-height: 1.6; }
.draft-section { margin-top: 20px; h3 { display: flex; align-items: baseline; gap: 8px; margin: 0 0 10px; color: #34525e; font-size: 13px; } h3 small { color: #89969a; font-size: 11px; font-weight: 400; } ul { margin: 0; padding-left: 19px; color: #596f79; font-size: 13px; line-height: 1.8; } }
.uncertainty { padding: 12px 14px; border-left: 3px solid #d9a75f; background: #fbf7ee; }
.citation { padding: 13px 14px; border: 1px solid #e6eeee; border-radius: 10px; background: #f9fcfb; & + & { margin-top: 9px; } p { margin: 9px 0 8px; color: #5a7079; font-size: 12px; line-height: 1.65; white-space: pre-wrap; } }
.citation-head { display: flex; align-items: flex-start; gap: 9px; }
.citation-index { display: grid; width: 20px; height: 20px; flex: none; place-items: center; border-radius: 6px; background: #e3f3f1; color: #167b7d; font-size: 11px; font-weight: 700; }
.citation-meta { display: flex; min-width: 0; flex: 1; flex-direction: column; gap: 4px; strong { color: #2d4c59; font-size: 13px; } span { color: #829198; font-size: 11px; line-height: 1.5; } }
.citation-foot { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding-top: 8px; border-top: 1px dashed #e3edeb; .chunk-id { color: #94a3a6; font-size: 10px; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; } a { color: #167b7d; font-size: 12px; text-decoration: none; } a:hover { text-decoration: underline; } }
@media (max-width: 520px) { .draft-panel { padding: 19px; } .signal-row { gap: 6px; } }
</style>
