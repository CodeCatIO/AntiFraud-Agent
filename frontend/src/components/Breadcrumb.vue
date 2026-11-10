<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

// 根据 route.matched 自动生成面包屑
const breadcrumbs = computed(() =>
  route.matched
    .filter((item) => item.meta?.title)
    .map((item) => ({
      path: item.path,
      title: item.meta.title,
    }))
)
</script>

<template>
  <el-breadcrumb separator="/">
    <el-breadcrumb-item
      v-for="(item, index) in breadcrumbs"
      :key="item.path"
      :to="index < breadcrumbs.length - 1 ? { path: item.path } : undefined"
    >
      {{ item.title }}
    </el-breadcrumb-item>
  </el-breadcrumb>
</template>
