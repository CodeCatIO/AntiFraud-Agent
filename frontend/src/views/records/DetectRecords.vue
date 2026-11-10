<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Search, Refresh, View } from '@element-plus/icons-vue'
import { getRecords } from '@/api/detect'

// 筛选参数
const filters = reactive({
  type: '',
})

// 分页
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(10)
const loading = ref(false)

// 列表数据
const records = ref([])

// 类型/等级/状态映射
const typeMap = {
  text: { label: '文本', tagType: 'primary' },
  voice: { label: '语音', tagType: 'success' },
  image: { label: '图像', tagType: 'warning' },
  composite: { label: '综合', tagType: 'primary' },
}
const riskMap = {
  高风险: 'danger',
  中风险: 'warning',
  低风险: 'info',
  安全: 'success',
}
const statusMap = {
  pending: { label: '待检测', tagType: 'info' },
  processing: { label: '检测中', tagType: 'primary' },
  completed: { label: '已完成', tagType: 'success' },
  failed: { label: '失败', tagType: 'danger' },
}

// 解析 detail JSON 字符串（后端存库为 JSON 字符串）
function parseDetail(detail) {
  if (detail == null) return {}
  if (typeof detail === 'object') return detail
  try {
    return JSON.parse(detail)
  } catch (e) {
    return { detail: String(detail) }
  }
}

// 格式化时间（兼容字符串 / 时间戳）
function formatTime(t) {
  if (!t) return ''
  if (typeof t === 'number') {
    const d = new Date(t)
    const p = (n) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
  }
  return String(t).replace('T', ' ').slice(0, 19)
}

// 加载列表（真实接口：GET /detect/records）
async function loadRecords() {
  loading.value = true
  try {
    const params = {
      pageNum: pageNum.value,
      pageSize: pageSize.value,
      type: filters.type || undefined,
    }
    const res = await getRecords(params)
    const list = res?.records || []

    const rows = list.map((r) => ({
      id: r.id,
      type: r.type,
      content: r.inputContent,
      risk_level: r.riskLevel,
      risk_score: r.riskScore,
      status: r.status || 'completed',
      created_at: formatTime(r.createTime),
      detail: parseDetail(r.detail),
    }))

    records.value = rows
    total.value = res?.total || 0
  } catch (e) {
    // 错误已由拦截器统一提示
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pageNum.value = 1
  loadRecords()
}

function handleReset() {
  filters.type = ''
  handleSearch()
}

function handlePageChange() {
  loadRecords()
}

// 详情弹窗
const detailVisible = ref(false)
const detailLoading = ref(false)
const currentRecord = ref(null)

async function handleView(row) {
  detailVisible.value = true
  detailLoading.value = true
  try {
    // 后端暂无单条详情接口，直接展示行内数据（detail 已解析为对象）
    await new Promise((resolve) => setTimeout(resolve, 100))
    currentRecord.value = row
  } catch (e) {
    detailVisible.value = false
  } finally {
    detailLoading.value = false
  }
}

// detail JSON 结构化展示：字段中文化 + 去重 + 格式化
const fieldLabels = {
  riskLevel: '风险等级',
  risk_score: '风险分数',
  elaScore: 'ELA 误差均值',
  confidence: '置信度',
  face_detected: '人脸检测',
  source: '检测来源',
  fakeProbability: '伪造概率',
  features: '特征数据',
  isFake: '是否伪造',
  ocr_text: 'OCR识别文字',
  analysis: '详细分析',
}

// 将原始 key（含驼峰/下划线变体）归一化为标准 key，未知字段返回 null
function canonicalKey(rawKey) {
  const k = String(rawKey).replace(/_/g, '').toLowerCase()
  if (k === 'risklevel') return 'riskLevel'
  if (k === 'riskscore') return 'risk_score'
  if (k === 'elascore') return 'elaScore'
  if (k === 'confidence') return 'confidence'
  if (k === 'facedetected') return 'face_detected'
  if (k === 'source') return 'source'
  if (k === 'fakeprobability') return 'fakeProbability'
  if (k === 'features') return 'features'
  if (k === 'isfake' || k === 'isfraud') return 'isFake'
  if (k === 'ocrtext') return 'ocr_text'
  if (k === 'analysis') return 'analysis'
  return null
}

// 按字段类型格式化值，空值返回 null（不显示该行）
function formatValue(key, value) {
  if (value === null || value === undefined || value === '') return null
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (key === 'confidence' || key === 'fakeProbability') {
    const num = Number(value)
    if (Number.isFinite(num)) {
      // 兼容 0.6677 与 66.77 两种取值范围
      const pct = num > 0 && num <= 1 ? num * 100 : num
      return `${pct.toFixed(2)}%`
    }
    return String(value)
  }
  if (key === 'risk_score') {
    const num = Number(value)
    return Number.isFinite(num) ? String(Math.round(num)) : String(value)
  }
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

const detailEntries = computed(() => {
  const detail = currentRecord.value?.detail
  if (!detail || typeof detail !== 'object') return []
  const seen = new Set()
  const entries = []
  for (const [rawKey, rawValue] of Object.entries(detail)) {
    const key = canonicalKey(rawKey)
    // 未知字段或重复字段（如 riskLevel 与 risk_level）跳过
    if (!key || seen.has(key)) continue
    const value = formatValue(key, rawValue)
    if (value === null) continue
    seen.add(key)
    entries.push({
      key,
      label: fieldLabels[key],
      value,
      pre: typeof rawValue === 'object' && rawValue !== null,
    })
  }
  return entries
})

onMounted(loadRecords)
</script>

<template>
  <div class="detect-records">
    <div class="page-heading"><h1>检测记录</h1><p>查看已提交的检测内容与分析结果。</p></div>
    <!-- 筛选栏 -->
    <el-card shadow="hover" class="filter-card">
      <el-form inline @submit.prevent>
        <el-form-item label="检测类型">
          <el-select v-model="filters.type" placeholder="全部" clearable style="width: 140px">
            <el-option label="文本" value="text" />
            <el-option label="语音" value="voice" />
            <el-option label="图像" value="image" />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 记录列表 -->
    <el-card shadow="hover">
      <el-table :data="records" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column label="检测类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="typeMap[row.type]?.tagType || 'info'">
              {{ typeMap[row.type]?.label || row.type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="输入内容摘要" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="content-text">{{ row.content }}</span>
          </template>
        </el-table-column>
        <el-table-column label="风险等级" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="riskMap[row.risk_level] || 'info'">{{ row.risk_level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="risk_score" label="风险分数" width="100" align="center" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusMap[row.status]?.tagType || 'info'">
              {{ statusMap[row.status]?.label || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="检测时间" width="170" align="center" />
        <el-table-column label="操作" width="90" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link :icon="View" @click="handleView(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="pageNum"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @current-change="handlePageChange"
          @size-change="handleSearch"
        />
      </div>
    </el-card>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="检测记录详情" width="640px" destroy-on-close>
      <div v-loading="detailLoading">
        <template v-if="currentRecord">
          <div class="detail-header">
            <el-tag :type="typeMap[currentRecord.type]?.tagType || 'info'">
              {{ typeMap[currentRecord.type]?.label || currentRecord.type }}
            </el-tag>
            <el-tag :type="riskMap[currentRecord.risk_level] || 'info'">
              {{ currentRecord.risk_level }}
            </el-tag>
            <el-tag :type="statusMap[currentRecord.status]?.tagType || 'info'">
              {{ statusMap[currentRecord.status]?.label || currentRecord.status }}
            </el-tag>
            <span class="detail-score">风险分数：{{ currentRecord.risk_score }}</span>
          </div>

          <div class="detail-block">
            <div class="block-label">输入内容</div>
            <p class="detail-content">{{ currentRecord.content }}</p>
          </div>

          <div class="detail-block">
            <div class="block-label">检测结果详情</div>
            <el-descriptions :column="1" border>
              <el-descriptions-item
                v-for="entry in detailEntries"
                :key="entry.key"
                :label="entry.label"
              >
                <pre v-if="entry.pre" class="detail-json">{{ entry.value }}</pre>
                <template v-else>{{ entry.value }}</template>
              </el-descriptions-item>
            </el-descriptions>
          </div>

          <div class="detail-block">
            <div class="block-label">检测时间</div>
            <span>{{ currentRecord.created_at }}</span>
          </div>
        </template>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.detect-records {
  max-width: 1440px;
  margin: 0 auto;
  .page-heading { margin-bottom: 24px; h1 { font-size: 27px; color: #172e43; } p { margin-top: 7px; color: #647887; } }
  .filter-card {
    margin-bottom: 18px;

    :deep(.el-form-item) {
      margin-bottom: 0;
    }
  }

  .content-text {
    color: #304d60;
  }

  .pagination {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
  }

  .detail-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 16px;

    .detail-score {
      font-size: 14px;
      font-weight: 600;
      color: #303133;
    }
  }

  .detail-block {
    margin-bottom: 16px;

    .block-label {
      font-size: 13px;
      font-weight: 600;
      color: #909399;
      margin-bottom: 8px;
    }

    .detail-content {
      font-size: 14px;
      line-height: 1.8;
      color: #365466;
      background: rgba(233, 247, 247, .62);
      border: 1px solid rgba(145, 185, 190, .22);
      border-radius: 10px;
      padding: 12px;
    }

    .detail-json {
      margin: 0;
      font-family: 'JetBrains Mono', Consolas, monospace;
      font-size: 12px;
      line-height: 1.6;
      color: #606266;
      white-space: pre-wrap;
      word-break: break-all;
    }
  }
}
</style>
