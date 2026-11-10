<script setup>
import { onMounted, reactive, ref } from 'vue'
import { Search, Refresh } from '@element-plus/icons-vue'

// ---------- 筛选与分页 ----------
const filters = reactive({
  operator: '',
  type: '',
  dateRange: [],
})

const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(10)
const loading = ref(false)

const logs = ref([])

// 操作类型 → 标签颜色
const typeMap = {
  登录: 'primary',
  检测: 'success',
  存证: 'warning',
  水印: 'primary',
  用户管理: 'danger',
  角色管理: 'danger',
  菜单管理: 'danger',
}

// 操作类型选项
const typeOptions = ['登录', '检测', '存证', '水印', '用户管理', '角色管理', '菜单管理']

// ---------- Mock 数据（接口通了以后删除） ----------
const mockLogs = [
  { id: 1, operator: 'admin', type: '登录', description: '用户登录成功', ip: '192.168.1.100', cost: 120, time: '2026-05-07 09:30:12' },
  { id: 2, operator: 'admin', type: '检测', description: '文本诈骗检测：内容长度 86 字符', ip: '192.168.1.100', cost: 1250, time: '2026-05-07 10:23:45' },
  { id: 3, operator: 'admin', type: '存证', description: '区块链存证：哈希 a3f5…d5f1', ip: '192.168.1.100', cost: 2100, time: '2026-05-07 14:32:10' },
  { id: 4, operator: 'admin', type: '水印', description: '嵌入水印：水印文字长度 16 字符', ip: '192.168.1.100', cost: 860, time: '2026-05-07 15:10:33' },
  { id: 5, operator: 'zhangsan', type: '检测', description: '语音诈骗检测：audio_20260506.wav', ip: '192.168.1.102', cost: 3400, time: '2026-05-06 15:30:12' },
  { id: 6, operator: 'zhangsan', type: '登录', description: '用户登录成功', ip: '192.168.1.102', cost: 95, time: '2026-05-06 09:12:08' },
  { id: 7, operator: 'admin', type: '用户管理', description: '新增用户：lisi', ip: '192.168.1.100', cost: 420, time: '2026-05-05 11:45:29' },
  { id: 8, operator: 'admin', type: '角色管理', description: '分配菜单：普通用户', ip: '192.168.1.100', cost: 380, time: '2026-05-05 11:48:55' },
  { id: 9, operator: 'lisi', type: '检测', description: '图片诈骗检测：screenshot.png', ip: '192.168.1.103', cost: 780, time: '2026-05-04 16:20:47' },
  { id: 10, operator: 'admin', type: '菜单管理', description: '编辑菜单：文本检测', ip: '192.168.1.100', cost: 60, time: '2026-05-03 10:05:16' },
]

// ---------- 加载列表 ----------
async function loadLogs() {
  loading.value = true
  try {
    // 接口未通前用 Mock 占位，接口通了以后替换为：
    // const params = {
    //   pageNum: pageNum.value,
    //   pageSize: pageSize.value,
    //   operator: filters.operator || undefined,
    //   type: filters.type || undefined,
    //   startTime: filters.dateRange?.[0] || undefined,
    //   endTime: filters.dateRange?.[1] || undefined,
    // }
    // const res = await getOpLogs(params)
    // logs.value = res.list || []
    // total.value = res.total || 0
    await new Promise((resolve) => setTimeout(resolve, 300))

    // Mock 筛选 + 分页
    let list = [...mockLogs]
    if (filters.operator) {
      list = list.filter((item) => item.operator.includes(filters.operator))
    }
    if (filters.type) {
      list = list.filter((item) => item.type === filters.type)
    }
    if (filters.dateRange?.length === 2) {
      const [start, end] = filters.dateRange
      list = list.filter((item) => item.time >= start && item.time <= `${end} 23:59:59`)
    }
    total.value = list.length
    const startIdx = (pageNum.value - 1) * pageSize.value
    logs.value = list.slice(startIdx, startIdx + pageSize.value)
  } catch (e) {
    // 错误已由拦截器统一提示
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pageNum.value = 1
  loadLogs()
}

function handleReset() {
  filters.operator = ''
  filters.type = ''
  filters.dateRange = []
  handleSearch()
}

// 耗时 → 颜色（<100 绿 / 100-500 黄 / >500 红）
function costColor(cost) {
  if (cost < 100) return '#67c23a'
  if (cost <= 500) return '#e6a23c'
  return '#f56c6c'
}

onMounted(loadLogs)
</script>

<template>
  <div class="op-log">
    <!-- 筛选栏 -->
    <el-card shadow="hover" class="filter-card">
      <el-form inline @submit.prevent>
        <el-form-item label="操作人">
          <el-input
            v-model="filters.operator"
            placeholder="请输入操作人"
            clearable
            style="width: 160px"
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          />
        </el-form-item>

        <el-form-item label="操作类型">
          <el-select v-model="filters.type" placeholder="全部" clearable style="width: 140px">
            <el-option v-for="t in typeOptions" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>

        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 260px"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 日志列表（只读） -->
    <el-card shadow="hover">
      <el-table :data="logs" v-loading="loading" stripe border>
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column prop="operator" label="操作人" width="120" />
        <el-table-column label="操作类型" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="typeMap[row.type] || 'info'">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="操作描述" min-width="240" show-overflow-tooltip />
        <el-table-column prop="ip" label="IP地址" width="130" />
        <el-table-column label="耗时(ms)" width="110" align="center">
          <template #default="{ row }">
            <span class="cost-text" :style="{ color: costColor(row.cost) }">{{ row.cost }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="time" label="操作时间" width="170" align="center" />
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
          @current-change="loadLogs"
          @size-change="handleSearch"
        />
      </div>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.op-log {
  .filter-card {
    margin-bottom: 16px;

    :deep(.el-form-item) {
      margin-bottom: 0;
    }
  }

  .cost-text {
    font-weight: 600;
  }

  .pagination {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
  }
}
</style>
