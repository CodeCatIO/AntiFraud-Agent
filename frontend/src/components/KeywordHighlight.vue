<script setup>
import { computed } from 'vue'

const props = defineProps({
  // 原始文本
  text: { type: String, default: '' },
  // 需要高亮的关键词数组
  keywords: { type: Array, default: () => [] },
})

// HTML 转义，防止注入
function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

// 正则特殊字符转义
function escapeRegExp(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

const highlightedHtml = computed(() => {
  const source = escapeHtml(props.text || '')
  const words = (props.keywords || []).filter((k) => k && String(k).trim())
  if (!words.length) return source

  // 按长度降序，优先匹配长关键词，避免短词抢先破坏长词
  const pattern = words
    .map((k) => escapeRegExp(escapeHtml(String(k))))
    .sort((a, b) => b.length - a.length)
    .join('|')

  const reg = new RegExp(`(${pattern})`, 'g')
  return source.replace(reg, '<mark>$1</mark>')
})
</script>

<template>
  <!-- eslint-disable-next-line vue/no-v-html -->
  <div class="keyword-highlight" v-html="highlightedHtml" />
</template>

<style scoped lang="scss">
.keyword-highlight {
  font-size: 14px;
  line-height: 1.8;
  color: #606266;
  word-break: break-all;

  :deep(mark) {
    background-color: #ffe58f;
    color: #d4380d;
    font-weight: 700;
    padding: 0 2px;
    border-radius: 2px;
  }
}
</style>
