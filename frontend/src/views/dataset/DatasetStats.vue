<script setup>
import { onMounted, onUnmounted, ref, nextTick } from 'vue'
import * as echarts from 'echarts/core'
import { PieChart, BarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getDatasetLabels } from '@/api/dataset'

echarts.use([
  PieChart,
  BarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  CanvasRenderer,
])

const loading = ref(false)
const data = ref(null)
const activeTab = ref('manual')

const charts = []
const chartRefs = {
  manual: ref(null),
  rule: ref(null),
  voice: ref(null),
  image: ref(null),
}

// 标签固定配色（风险越高越红）
const COLORS_SAFE = ['#67c23a', '#f56c6c', '#e6a23c', '#f89898', '#b37feb']
const COLORS_FRAUD = [
  '#f56c6c', '#e6a23c', '#ff8c69', '#b37feb', '#409eff',
  '#36cfc9', '#73d13d', '#9254de', '#597ef7', '#ff7a45', '#909399',
]

function donutOption(title, items, colors) {
  return {
    title: { text: title, left: 'center' },
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)',
    },
    legend: { bottom: 0, type: 'scroll' },
    series: [
      {
        type: 'pie',
        radius: ['42%', '66%'],
        center: ['50%', '46%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
        label: { formatter: '{b}\n{d}%' },
        data: items.map((it, i) => ({
          name: it.name,
          value: it.value,
          itemStyle: { color: colors[i % colors.length] },
        })),
      },
    ],
  }
}

function ruleBarOption(items) {
  const sorted = [...items].sort((a, b) => a.value - b.value)
  return {
    title: { text: '诈骗文本作案手法分布（规则推断）', left: 'center' },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 130, right: 40, top: 50, bottom: 30 },
    xAxis: { type: 'value', minInterval: 1 },
    yAxis: { type: 'category', data: sorted.map((it) => it.name) },
    series: [
      {
        type: 'bar',
        barWidth: 16,
        data: sorted.map((it, i) => ({
          value: it.value,
          // 兜底类灰色
          itemStyle: {
            color: it.name === '其他诈骗手法' ? '#909399' : COLORS_FRAUD[i % COLORS_FRAUD.length],
            borderRadius: [0, 4, 4, 0],
          },
        })),
        label: { show: true, position: 'right' },
      },
    ],
  }
}

function renderCharts() {
  charts.forEach((c) => c.dispose())
  charts.length = 0
  if (!data.value) return
  const d = data.value

  if (d.text?.manual && chartRefs.manual.value) {
    const c = echarts.init(chartRefs.manual.value)
    c.setOption(donutOption('文本人工标注类别', d.text.manual.items, COLORS_SAFE))
    charts.push(c)
  }
  if (d.text?.rule && chartRefs.rule.value) {
    const c = echarts.init(chartRefs.rule.value)
    c.setOption(ruleBarOption(d.text.rule.items))
    charts.push(c)
  }
  if (d.voice && chartRefs.voice.value) {
    const c = echarts.init(chartRefs.voice.value)
    c.setOption(donutOption('语音真伪标签', d.voice.items, COLORS_SAFE))
    charts.push(c)
  }
  if (d.image && chartRefs.image.value) {
    const c = echarts.init(chartRefs.image.value)
    c.setOption(donutOption('图像真伪标签', d.image.items, COLORS_SAFE))
    charts.push(c)
  }
}

async function loadData() {
  loading.value = true
  try {
    data.value = await getDatasetLabels()
    await nextTick()
    renderCharts()
  } finally {
    loading.value = false
  }
}

function handleResize() {
  charts.forEach((c) => c.resize())
}

onMounted(async () => {
  await loadData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  charts.forEach((c) => c.dispose())
})
</script>

<template>
  <div v-loading="loading" class="dataset-page">
    <template v-if="data">
      <!-- 顶部统计卡片 -->
      <el-row :gutter="16" class="stats-row">
        <el-col :xs="24" :sm="8">
          <el-card shadow="hover">
            <el-statistic title="文本样本总量" :value="data.text?.total ?? 0" />
            <div class="card-sub">
              正常 {{ data.text?.normalTotal }} / 诈骗 {{ data.text?.fraudTotal }}
            </div>
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="8">
          <el-card shadow="hover">
            <el-statistic title="语音样本总量" :value="data.voice?.total ?? 0" />
            <div class="card-sub">
              真人 {{ data.voice?.items?.[0]?.value }} /
              AI合成 {{ data.voice?.items?.[1]?.value }}
              <template v-if="data.voice?.durationMin">
                ，共 {{ data.voice.durationMin }} 分钟
              </template>
            </div>
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="8">
          <el-card shadow="hover">
            <el-statistic title="图像样本总量" :value="data.image?.total ?? 0" />
            <div class="card-sub">
              真实 {{ data.image?.items?.[0]?.value }} /
              AI生成 {{ data.image?.items?.[1]?.value }} /
              篡改 {{ data.image?.items?.[2]?.value }}
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 文本标签 -->
      <el-card v-if="data.text" shadow="hover" class="block-card">
        <template #header>
          <div class="card-header">
            <span>文本数据集标签分布</span>
            <el-tag type="info" effect="plain">
              规则细分覆盖率 {{ data.text.rule.coverage }}%
            </el-tag>
          </div>
        </template>
        <el-alert type="info" :closable="false" show-icon class="hint-alert">
          <template #title>
            左图为训练集人工真实标注（{{ data.text.manual.source }}）；
            右图为关键词规则对诈骗文本的自动手法推断（{{ data.text.rule.source }}），
            命中不了的归入「其他诈骗手法」，两种口径并存、不互相替代。
          </template>
        </el-alert>
        <el-row :gutter="16">
          <el-col :xs="24" :md="10">
            <div ref="manual" class="chart square-chart" />
          </el-col>
          <el-col :xs="24" :md="14">
            <div ref="rule" class="chart wide-chart" />
          </el-col>
        </el-row>
      </el-card>

      <!-- 语音 / 图像标签 -->
      <el-row :gutter="16" class="block-row">
        <el-col :xs="24" :md="12">
          <el-card shadow="hover">
            <template #header>语音数据集（判真伪，不判说话内容）</template>
            <div ref="voice" class="chart" />
          </el-card>
        </el-col>
        <el-col :xs="24" :md="12">
          <el-card shadow="hover">
            <template #header>图像数据集（判真伪，不判画面主题）</template>
            <div ref="image" class="chart" />
          </el-card>
        </el-col>
      </el-row>

      <!-- 标签明细 + 样例 -->
      <el-card shadow="hover" class="block-card">
        <template #header>标签明细与真实样例</template>
        <el-tabs v-model="activeTab">
          <el-tab-pane label="文本·人工标注" name="manual">
            <el-table :data="data.text?.manual?.items ?? []" stripe>
              <el-table-column prop="name" label="标签" width="220" />
              <el-table-column prop="value" label="样本数" width="100" sortable />
              <el-table-column prop="desc" label="含义" min-width="220" />
              <el-table-column label="训练集样例" min-width="320">
                <template #default="{ row }">
                  <div v-for="(ex, i) in row.examples" :key="i" class="example-line">
                    {{ ex }}
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="文本·规则细分手法" name="rule">
            <el-table :data="data.text?.rule?.items ?? []" stripe>
              <el-table-column prop="name" label="手法标签" width="220" />
              <el-table-column prop="value" label="命中文本数" width="120" sortable />
              <el-table-column label="命中样例" min-width="400">
                <template #default="{ row }">
                  <div v-if="!row.examples?.length" class="muted">无样例</div>
                  <div v-for="(ex, i) in row.examples" :key="i" class="example-line">
                    {{ ex }}
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="语音标签" name="voice">
            <el-table :data="data.voice?.items ?? []" stripe>
              <el-table-column prop="name" label="标签" width="180" />
              <el-table-column prop="value" label="样本数" width="120" sortable />
              <el-table-column prop="desc" label="含义" min-width="300" />
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="图像标签" name="image">
            <el-table :data="data.image?.items ?? []" stripe>
              <el-table-column prop="name" label="标签" width="180" />
              <el-table-column prop="value" label="样本数" width="120" sortable />
              <el-table-column prop="desc" label="含义" min-width="300" />
            </el-table>
          </el-tab-pane>
        </el-tabs>
        <div class="generated-at">
          统计生成时间：{{ data.generatedAt }}
        </div>
      </el-card>
    </template>
  </div>
</template>

<style scoped lang="scss">
.dataset-page {
  .stats-row {
    margin-bottom: 16px;

    .el-col {
      margin-bottom: 16px;
    }
  }

  .card-sub {
    margin-top: 8px;
    font-size: 13px;
    color: #909399;
  }

  .block-card {
    margin-bottom: 16px;
  }

  .block-row {
    margin-bottom: 16px;

    .el-col {
      margin-bottom: 16px;
    }
  }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .hint-alert {
    margin-bottom: 12px;
  }

  .chart {
    width: 100%;
    height: 340px;
  }

  .square-chart {
    height: 380px;
  }

  .wide-chart {
    height: 380px;
  }

  .example-line {
    font-size: 13px;
    color: #606266;
    line-height: 1.7;
  }

  .muted {
    color: #c0c4cc;
  }

  .generated-at {
    margin-top: 12px;
    text-align: right;
    font-size: 12px;
    color: #c0c4cc;
  }
}
</style>
