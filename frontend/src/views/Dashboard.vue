<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { ArrowRight, ChatLineSquare, Microphone, Picture } from '@element-plus/icons-vue'
import { getStats, getTrend } from '@/api/dashboard'
import { getRecords } from '@/api/detect'

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])
const router = useRouter()
const loading = ref(true)
const error = ref(false)
const trendError = ref(false)
const recordsError = ref(false)
const stats = ref(null)
const trend = ref([])
const recentRecords = ref([])
const chartRef = ref(null)
let chart = null

const channels = computed(() => [
  { label: '文本检测', count: Number(stats.value?.moduleUsage?.text || 0), icon: ChatLineSquare, path: '/detect/text' },
  { label: '语音检测', count: Number(stats.value?.moduleUsage?.voice || 0), icon: Microphone, path: '/detect/voice' },
  { label: '图片检测', count: Number(stats.value?.moduleUsage?.image || 0), icon: Picture, path: '/detect/image' },
])
const maxChannel = computed(() => Math.max(...channels.value.map((item) => item.count), 1))
const hasTrend = computed(() => trend.value.some((item) => Number(item.total) > 0))

function drawChart() {
  if (!chartRef.value || !hasTrend.value) return
  chart?.dispose()
  chart = echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis', backgroundColor: '#152b43', borderWidth: 0, textStyle: { color: '#fff' } },
    grid: { left: 34, right: 16, top: 20, bottom: 28 },
    xAxis: { type: 'category', boundaryGap: false, data: trend.value.map((item) => item.date?.slice(5)), axisLine: { lineStyle: { color: '#dce4e9' } }, axisLabel: { color: '#627485' } },
    yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#edf1f3' } }, axisLabel: { color: '#627485' } },
    series: [{ type: 'line', data: trend.value.map((item) => Number(item.total) || 0), smooth: 0.25, symbolSize: 7, lineStyle: { color: '#167b81', width: 3 }, itemStyle: { color: '#167b81' }, areaStyle: { color: 'rgba(22, 123, 129, 0.12)' } }],
  })
}

async function loadData() {
  loading.value = true
  error.value = false
  trendError.value = false
  recordsError.value = false
  try {
    stats.value = await getStats()
    const [trendResult, recordsResult] = await Promise.allSettled([
      getTrend(), getRecords({ pageNum: 1, pageSize: 5 }),
    ])
    trendError.value = trendResult.status === 'rejected'
    recordsError.value = recordsResult.status === 'rejected'
    trend.value = trendResult.status === 'fulfilled' && Array.isArray(trendResult.value) ? trendResult.value : []
    recentRecords.value = recordsResult.status === 'fulfilled' ? recordsResult.value?.records || [] : []
    await nextTick()
    drawChart()
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function resizeChart() { chart?.resize() }
onMounted(() => { loadData(); window.addEventListener('resize', resizeChart) })
onUnmounted(() => { window.removeEventListener('resize', resizeChart); chart?.dispose() })
</script>

<template>
  <div class="dashboard">
    <div class="page-heading">
      <div><h1>反诈工作台</h1><p>从一次检测开始，查看近期风险与处理记录。</p></div>
      <el-button type="primary" :icon="ArrowRight" @click="router.push('/detect/text')">开始文本检测</el-button>
    </div>

    <el-alert v-if="error" title="数据加载失败，请检查服务连接后重试。" type="error" show-icon :closable="false" class="load-error">
      <template #default><el-button link type="primary" @click="loadData">重新加载</el-button></template>
    </el-alert>

    <div v-else v-loading="loading" class="dashboard-content">
      <div class="stats-grid">
        <div class="stat stat-primary"><span>累计检测</span><strong>{{ stats?.totalDetections ?? '—' }}</strong><small>本账号的检测记录</small></div>
        <div class="stat"><span>今日检测</span><strong>{{ stats?.todayDetections ?? '—' }}</strong><small>今日新增</small></div>
        <div class="stat"><span>高风险记录</span><strong>{{ stats?.highRiskCount ?? '—' }}</strong><small>占全部检测 {{ stats?.highRiskRatio ?? '—' }}%</small></div>
        <div class="stat"><span>存证记录</span><strong>{{ stats?.totalCerts ?? '—' }}</strong><small>今日新增 {{ stats?.todayCerts ?? '—' }}</small></div>
      </div>

      <div class="overview-grid">
        <section class="panel trend-panel">
          <div class="panel-heading"><div><h2>近 7 天检测趋势</h2><p>按检测日期统计</p></div></div>
          <div v-if="hasTrend" ref="chartRef" class="trend-chart" role="img" aria-label="近 7 天检测次数趋势" />
          <div v-else-if="trendError" class="panel-empty">趋势数据暂时无法加载。</div>
          <div v-else class="panel-empty">近 7 天暂无检测数据，完成检测后可在这里查看趋势。</div>
        </section>
        <section class="panel channels-panel">
          <div class="panel-heading"><div><h2>检测方式</h2><p>按累计使用次数统计</p></div></div>
          <button v-for="item in channels" :key="item.path" class="channel" type="button" @click="router.push(item.path)">
            <span class="channel-icon"><el-icon><component :is="item.icon" /></el-icon></span>
            <span class="channel-body"><span class="channel-name">{{ item.label }} <b>{{ item.count }}</b></span><span class="channel-track"><i :style="{ width: (item.count / maxChannel * 100) + '%' }" /></span></span>
            <el-icon class="channel-arrow"><ArrowRight /></el-icon>
          </button>
        </section>
      </div>

      <section class="panel recent-panel">
        <div class="panel-heading"><div><h2>近期检测记录</h2><p>快速查看最近提交的内容与风险等级</p></div><el-button link type="primary" @click="router.push('/records')">查看全部 <el-icon><ArrowRight /></el-icon></el-button></div>
        <div v-if="recentRecords.length" class="recent-list">
          <div v-for="record in recentRecords" :key="record.id" class="recent-row">
            <span class="record-type">{{ { text: '文本', voice: '语音', image: '图片' }[record.type] || '综合' }}</span>
            <span class="record-summary">{{ record.inputContent || '文件检测' }}</span>
            <el-tag :type="{ 高风险: 'danger', 中风险: 'warning', 安全: 'success' }[record.riskLevel] || 'info'" effect="light">{{ record.riskLevel || '待评估' }}</el-tag>
            <time>{{ String(record.createTime || '').replace('T', ' ').slice(0, 16) }}</time>
          </div>
        </div>
        <div v-else class="panel-empty">{{ recordsError ? '检测记录暂时无法加载。' : '还没有检测记录。可以先从文本、语音或图片检测开始。' }}</div>
      </section>
    </div>
  </div>
</template>

<style scoped lang="scss">
.dashboard { max-width: 1440px; margin: 0 auto; }
.page-heading { display: flex; justify-content: space-between; align-items: center; gap: 20px; margin-bottom: 30px; h1 { font-size: 29px; color: #15364b; letter-spacing: -.025em; } p { margin-top: 8px; color: #506b7a; } :deep(.el-button--primary) { min-height: 40px; border-radius: 10px; background: linear-gradient(115deg, #17868c, #0d6877); border-color: #197b83; box-shadow: 0 9px 20px rgba(16, 105, 118, .18), inset 0 1px rgba(255, 255, 255, .2); } }
.load-error { margin-bottom: 20px; }
.stats-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin-bottom: 18px; }
.stat { min-height: 148px; padding: 23px 24px; background: linear-gradient(145deg, rgba(255, 255, 255, .83), rgba(246, 254, 254, .58)); border: 1px solid rgba(255, 255, 255, .9); border-radius: 18px; box-shadow: var(--surface-glass-shadow); backdrop-filter: blur(16px) saturate(1.18); -webkit-backdrop-filter: blur(16px) saturate(1.18); display: flex; flex-direction: column; position: relative; overflow: hidden; span, strong, small { position: relative; z-index: 1; } span { color: #4e6675; font-size: 14px; } strong { margin: 13px 0 7px; color: #17334a; font-size: 31px; line-height: 1; font-variant-numeric: tabular-nums; letter-spacing: -.025em; } small { color: #587182; } }
.stat::before { content: ''; position: absolute; inset: 0; background: radial-gradient(ellipse 120px 72px at 100% 0%, rgba(147, 217, 220, .24), transparent 100%); pointer-events: none; }
.stat-primary { background: linear-gradient(135deg, #143e51 0%, #176877 58%, #288994 100%); border-color: rgba(191, 236, 236, .36); box-shadow: 0 17px 32px rgba(16, 91, 106, .21), inset 0 1px rgba(255, 255, 255, .24); span, strong, small { color: #fff; } small { opacity: .9; } }
.stat-primary::before { background: radial-gradient(ellipse 190px 150px at 100% 0%, rgba(170, 246, 235, .27), transparent 100%); }
.overview-grid { display: grid; grid-template-columns: minmax(0, 1.65fr) minmax(280px, 1fr); gap: 18px; margin-bottom: 18px; }
.panel { background: linear-gradient(145deg, rgba(255, 255, 255, .82), rgba(250, 254, 254, .66)); border: 1px solid rgba(255, 255, 255, .92); border-radius: 18px; padding: 23px 24px; box-shadow: var(--surface-glass-shadow); backdrop-filter: blur(16px) saturate(1.18); -webkit-backdrop-filter: blur(16px) saturate(1.18); }
.panel-heading { display: flex; justify-content: space-between; align-items: start; gap: 12px; margin-bottom: 22px; h2 { font-size: 17px; color: #19344a; } p { margin-top: 5px; color: #687a88; font-size: 13px; } }
.trend-chart { height: 260px; width: 100%; }
.panel-empty { min-height: 180px; display: grid; place-items: center; text-align: center; color: #657989; font-size: 14px; line-height: 1.7; }
.channel { width: 100%; display: flex; align-items: center; gap: 13px; border: 0; background: transparent; padding: 13px 0; cursor: pointer; text-align: left; border-top: 1px solid #eef2f3; color: #19344a; &:hover .channel-arrow { transform: translateX(3px); color: #167b81; } }
.channel-icon { display: grid; place-items: center; width: 36px; height: 36px; flex: none; border-radius: 11px; background: rgba(212, 241, 240, .78); border: 1px solid rgba(255, 255, 255, .8); box-shadow: inset 0 1px rgba(255, 255, 255, .8); color: #126e78; font-size: 18px; }
.channel-body { flex: 1; min-width: 0; }.channel-name { display: flex; justify-content: space-between; font-size: 14px; b { font-variant-numeric: tabular-nums; } }.channel-track { display: block; height: 5px; margin-top: 9px; background: #edf2f3; border-radius: 6px; overflow: hidden; i { display: block; height: 100%; background: #167b81; border-radius: inherit; } }.channel-arrow { transition: transform .2s ease; }
.recent-panel .panel-heading { margin-bottom: 9px; }.recent-list { overflow-x: auto; }.recent-row { display: grid; grid-template-columns: 68px minmax(180px, 1fr) 88px 145px; align-items: center; gap: 18px; min-width: 580px; padding: 14px 0; border-top: 1px solid #edf1f3; font-size: 13px; }.record-type { color: #42687a; font-weight: 600; }.record-summary { color: #21394c; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }.recent-row time { color: #687a88; text-align: right; font-variant-numeric: tabular-nums; }
@media (max-width: 1050px) { .stats-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.overview-grid { grid-template-columns: 1fr; } }
@media (max-width: 600px) { .page-heading { align-items: start; flex-direction: column; h1 { font-size: 23px; } }.stats-grid { gap: 10px; }.stat { min-height: 128px; padding: 17px; strong { font-size: 25px; } }.panel { padding: 18px; } }
@supports not (backdrop-filter: blur(1px)) {
  .stat:not(.stat-primary), .panel { background: #fff; }
}
@media (prefers-reduced-transparency: reduce) {
  .stat:not(.stat-primary), .panel { background: #fff; backdrop-filter: none; -webkit-backdrop-filter: none; }
}
</style>
