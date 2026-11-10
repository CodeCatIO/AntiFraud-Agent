<script setup>
import { reactive } from 'vue'

defineProps({ busy: Boolean })
const emit = defineEmits(['submit'])
const form = reactive({ decision: 'approve', comment: '', summary: '' })

function submit() {
  const edits = form.decision === 'modify' && form.summary.trim()
    ? { summary: form.summary.trim() }
    : {}
  if (form.decision === 'modify' && !edits.summary) return
  emit('submit', {
    decision: form.decision,
    comment: form.comment.trim(),
    edits,
  })
}
</script>

<template>
  <section class="review-panel">
    <header><div><span>HUMAN DECISION</span><h2>人工复核</h2></div><el-tag type="warning" effect="plain">检测证据与引用不可编辑</el-tag></header>
    <el-form label-position="top" @submit.prevent="submit">
      <el-form-item label="复核决定">
        <el-radio-group v-model="form.decision" class="decision-group">
          <el-radio-button value="approve">通过</el-radio-button>
          <el-radio-button value="modify">修改摘要后通过</el-radio-button>
          <el-radio-button value="return">退回并结束本次运行</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item v-if="form.decision === 'modify'" label="审核后的摘要" required>
        <el-input v-model="form.summary" type="textarea" :rows="3" maxlength="2000" show-word-limit placeholder="仅可调整研判摘要；风险检测结果与知识引用保持原样。" />
      </el-form-item>
      <el-form-item label="审核说明">
        <el-input v-model="form.comment" type="textarea" :rows="2" maxlength="2000" placeholder="记录判断依据、限制或退回原因（可选）" />
      </el-form-item>
      <div class="review-footer"><p>提交后会记录审核人、决定和修改内容。</p><el-button type="primary" :loading="busy" @click="submit">提交审核</el-button></div>
    </el-form>
  </section>
</template>

<style scoped lang="scss">
.review-panel { padding: 23px 24px; border: 1px solid #e5e6d5; border-radius: 14px; background: #fffdf7; }
header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 18px; span { color: #9b7a3d; font-size: 10px; font-weight: 700; letter-spacing: .12em; } h2 { margin: 4px 0 0; color: #4b4837; font-size: 17px; } }
.review-panel :deep(.el-form-item__label) { color: #5a5749; font-size: 13px; font-weight: 600; }
.decision-group { display: flex; flex-wrap: wrap; gap: 8px; :deep(.el-radio-button__inner) { border: 1px solid #d9ded6; border-radius: 8px !important; box-shadow: none !important; } }
.review-footer { display: flex; align-items: center; justify-content: space-between; gap: 14px; p { margin: 0; color: #858172; font-size: 11px; line-height: 1.5; } }
@media (max-width: 620px) { header { flex-direction: column; } .review-footer { align-items: stretch; flex-direction: column; } }
</style>
