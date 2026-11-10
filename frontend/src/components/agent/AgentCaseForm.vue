<script setup>
import { reactive, shallowRef } from 'vue'
import { DocumentAdd } from '@element-plus/icons-vue'

defineProps({ busy: Boolean })
const emit = defineEmits(['submit'])

const formRef = shallowRef(null)
const form = reactive({ content: '', source: '即时通信' })
const rules = {
  content: [
    { required: true, message: '请粘贴需要研判的文本线索', trigger: 'blur' },
    { min: 4, max: 10000, message: '线索长度应为 4 至 10000 个字符', trigger: 'blur' },
  ],
}

async function submit() {
  try {
    await formRef.value?.validate()
    emit('submit', { content: form.content.trim(), source: form.source })
  } catch {
    return
  }
}
</script>

<template>
  <section class="case-form panel">
    <header class="panel-heading">
      <div><h2>新建研判任务</h2><p>提交文本线索，生成可追溯、待人工确认的研判草稿。</p></div>
      <span class="heading-mark"><el-icon><DocumentAdd /></el-icon></span>
    </header>
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="submit">
      <el-form-item label="线索来源" prop="source">
        <el-select v-model="form.source" class="source-select">
          <el-option label="即时通信" value="即时通信" />
          <el-option label="短信" value="短信" />
          <el-option label="电话记录" value="电话记录" />
          <el-option label="网站或应用" value="网站或应用" />
          <el-option label="其他" value="其他" />
        </el-select>
      </el-form-item>
      <el-form-item label="线索文本" prop="content">
        <el-input
          v-model="form.content"
          type="textarea"
          :rows="8"
          maxlength="10000"
          show-word-limit
          resize="vertical"
          placeholder="粘贴短信、聊天内容或来电描述。请先移除姓名、手机号、账号、验证码等个人敏感信息。"
        />
      </el-form-item>
      <div class="privacy-note"><span class="privacy-dot" />请使用合成或脱敏文本；系统只提供辅助研判，不替代人工核实。</div>
      <div class="form-actions">
        <el-button type="primary" size="large" native-type="submit" :loading="busy">提交并开始研判</el-button>
      </div>
    </el-form>
  </section>
</template>

<style scoped lang="scss">
.panel { border: 1px solid #dce9e8; border-radius: 16px; background: #fff; box-shadow: 0 14px 34px rgba(24, 63, 73, .055); }
.case-form { padding: 25px; }
.panel-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 23px; h2 { margin: 0; color: #19384a; font-size: 19px; } p { margin: 7px 0 0; color: #71838b; font-size: 13px; line-height: 1.6; } }
.heading-mark { width: 40px; height: 40px; display: grid; place-items: center; flex: none; border-radius: 12px; background: #e8f5f2; color: #13747a; font-size: 19px; }
.source-select { width: 100%; max-width: 250px; }
.case-form :deep(.el-form-item__label) { color: #365460; font-weight: 600; }
.case-form :deep(.el-textarea__inner) { min-height: 190px !important; padding: 13px 15px; line-height: 1.75; }
.privacy-note { display: flex; align-items: center; gap: 8px; color: #71838b; font-size: 12px; line-height: 1.55; }
.privacy-dot { width: 7px; height: 7px; flex: none; border-radius: 50%; background: #4d9b8e; }
.form-actions { display: flex; justify-content: flex-end; margin-top: 20px; }
@media (max-width: 600px) { .case-form { padding: 19px; } .form-actions .el-button { width: 100%; } }
</style>
