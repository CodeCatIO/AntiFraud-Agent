<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Link, CopyDocument, Check, Close } from '@element-plus/icons-vue'
import { certBlockchain, verifyBlockchain } from '@/api/blockchain'

// ---------- 内容存证 ----------
const certContent = ref('')
const certLoading = ref(false)
const certResult = ref(null)

async function handleCert() {
  if (!certContent.value.trim()) {
    ElMessage.warning('请输入要存证的内容')
    return
  }
  certLoading.value = true
  try {
    // 接口未通前用 Mock 占位，接口通了以后替换为：
    // const res = await certBlockchain({ content: certContent.value })
    // certResult.value = res
    await new Promise((resolve) => setTimeout(resolve, 1000))
    certResult.value = {
      hash: 'a3f5c8e92b1d74f60a8e3c5b9d2f1a7e4c8b6d3f2a9e5c1b7d4f8a2e6c9b3d5f1',
      blockIndex: 128,
      certTime: '2026-05-07 14:32:10',
      valid: true,
    }
    ElMessage.success('存证成功')
    loadRecords()
  } catch (e) {
    // 错误已由拦截器统一提示
  } finally {
    certLoading.value = false
  }
}

// ---------- 存证验证 ----------
const verifyHash = ref('')
const verifyLoading = ref(false)
const verifyResult = ref(null) // true 通过 / false 不通过 / null 未验证

async function handleVerify() {
  if (!verifyHash.value.trim()) {
    ElMessage.warning('请输入要验证的哈希值')
    return
  }
  verifyLoading.value = true
  verifyResult.value = null
  try {
    // 接口未通前用 Mock 占位，接口通了以后替换为：
    // const res = await verifyBlockchain(verifyHash.value)
    // verifyResult.value = !!res.valid
    await new Promise((resolve) => setTimeout(resolve, 800))
    // Mock：与上面存证哈希一致则通过
    verifyResult.value =
      verifyHash.value === 'a3f5c8e92b1d74f60a8e3c5b9d2f1a7e4c8b6d3f2a9e5c1b7d4f8a2e6c9b3d5f1'
  } catch (e) {
    // 错误已由拦截器统一提示
  } finally {
    verifyLoading.value = false
  }
}

// ---------- 复制 ----------
async function handleCopy(text) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
  } catch {
    // 兼容非 https 环境
    const textarea = document.createElement('textarea')
    textarea.value = text
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    ElMessage.success('已复制到剪贴板')
  }
}

// ---------- 存证记录列表 ----------
const records = ref([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(10)
const loading = ref(false)

// Mock 数据（接口通了以后删除）
const mockRecords = [
  {
    id: 1,
    content: '诈骗短信证据：恭喜您中奖100万元，请点击链接领取……',
    hash: 'a3f5c8e92b1d74f60a8e3c5b9d2f1a7e4c8b6d3f2a9e5c1b7d4f8a2e6c9b3d5f1',
    blockIndex: 128,
    certTime: '2026-05-07 14:32:10',
    valid: true,
  },
  {
    id: 2,
    content: '诈骗电话录音证据：冒充银行客服索要验证码（45秒）',
    hash: 'e7b2d9f4a1c6e3b8d5a2f9c4e1b7d3a8f5c2e9b4d1a7f3c5e8b2d9f4a1c6e3b8',
    blockIndex: 127,
    certTime: '2026-05-06 10:15:43',
    valid: true,
  },
  {
    id: 3,
    content: '钓鱼网站截图证据：仿冒网银登录页面（1024x768）',
    hash: 'b9f2e5c8a1d4f7b3e6c9a2d5f8b1e4c7a3d6f9b2e5c8a1d4f7b3e6c9a2d5f8b1e4',
    blockIndex: 126,
    certTime: '2026-05-05 16:48:02',
    valid: true,
  },
  {
    id: 4,
    content: '聊天记录证据：冒充领导要求紧急转账 20 万元',
    hash: 'd1a4f7b3e6c9a2d5f8b1e4c7a3d6f9b2e5c8a1d4f7b3e6c9a2d5f8b1e4c7a3d6f',
    blockIndex: 125,
    certTime: '2026-05-04 09:23:55',
    valid: false,
  },
  {
    id: 5,
    content: '可疑二维码图片证据：扫码诱导下载未知 App',
    hash: 'f8b1e4c7a3d6f9b2e5c8a1d4f7b3e6c9a2d5f8b1e4c7a3d6f9b2e5c8a1d4f7b3',
    blockIndex: 124,
    certTime: '2026-05-03 11:37:29',
    valid: true,
  },
]

async function loadRecords() {
  loading.value = true
  try {
    // 接口未通前用 Mock 占位，接口通了以后替换为：
    // const res = await getRecords({ pageNum: pageNum.value, pageSize: pageSize.value })
    // records.value = res.list || []
    // total.value = res.total || 0
    await new Promise((resolve) => setTimeout(resolve, 300))
    const startIdx = (pageNum.value - 1) * pageSize.value
    records.value = mockRecords.slice(startIdx, startIdx + pageSize.value)
    total.value = mockRecords.length
  } catch (e) {
    // 错误已由拦截器统一提示
  } finally {
    loading.value = false
  }
}

function handlePageChange() {
  loadRecords()
}

onMounted(loadRecords)
</script>

<template>
  <div class="blockchain-cert">
    <!-- 上方：两个操作卡片 -->
    <el-row :gutter="16" class="top-row">
      <!-- 卡片1：内容存证 -->
      <el-col :xs="24" :md="12">
        <el-card shadow="hover">
          <template #header>
            <span class="card-title">内容存证</span>
          </template>

          <el-input
            v-model="certContent"
            type="textarea"
            :rows="5"
            maxlength="1000"
            show-word-limit
            placeholder="请输入要存证的内容，如诈骗证据文本描述等"
          />

          <el-button
            type="primary"
            :icon="Link"
            :loading="certLoading"
            class="cert-btn"
            @click="handleCert"
          >
            存证
          </el-button>

          <!-- 存证结果 -->
          <div v-if="certResult" class="cert-result">
            <div class="result-item">
              <span class="item-label">存证哈希（SHA-256）</span>
              <div class="hash-line">
                <code class="hash-text">{{ certResult.hash }}</code>
                <el-button :icon="CopyDocument" link type="primary" @click="handleCopy(certResult.hash)" />
              </div>
            </div>
            <div class="result-item">
              <span class="item-label">区块索引</span>
              <span class="block-index">#{{ certResult.blockIndex }}</span>
            </div>
            <div class="result-item">
              <span class="item-label">存证时间</span>
              <span>{{ certResult.certTime }}</span>
            </div>
            <div class="result-item">
              <span class="item-label">状态</span>
              <el-tag :type="certResult.valid ? 'success' : 'danger'">
                {{ certResult.valid ? '有效' : '无效' }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 卡片2：存证验证 -->
      <el-col :xs="24" :md="12">
        <el-card shadow="hover">
          <template #header>
            <span class="card-title">存证验证</span>
          </template>

          <el-input
            v-model="verifyHash"
            placeholder="请输入要验证的存证哈希值（SHA-256）"
            clearable
          />

          <el-button
            type="primary"
            :icon="Link"
            :loading="verifyLoading"
            class="cert-btn"
            @click="handleVerify"
          >
            验证
          </el-button>

          <!-- 验证结果 -->
          <div v-if="verifyResult === true" class="verify-result success">
            <el-icon :size="22"><Check /></el-icon>
            <span>存证有效</span>
          </div>
          <div v-else-if="verifyResult === false" class="verify-result fail">
            <el-icon :size="22"><Close /></el-icon>
            <span>验证失败</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 下方：存证记录列表 -->
    <el-card shadow="hover">
      <template #header>
        <span class="card-title">存证记录</span>
      </template>

      <el-table :data="records" v-loading="loading" stripe border>
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column prop="content" label="内容摘要" min-width="220" show-overflow-tooltip />
        <el-table-column label="内容哈希" min-width="200">
          <template #default="{ row }">
            <div class="hash-line">
              <code class="hash-text">{{ row.hash.slice(0, 16) }}…{{ row.hash.slice(-8) }}</code>
              <el-button :icon="CopyDocument" link type="primary" @click="handleCopy(row.hash)" />
            </div>
          </template>
        </el-table-column>
        <el-table-column label="区块索引" width="100" align="center">
          <template #default="{ row }">#{{ row.blockIndex }}</template>
        </el-table-column>
        <el-table-column prop="certTime" label="存证时间" width="170" align="center" />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.valid ? 'success' : 'danger'">
              {{ row.valid ? '有效' : '无效' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="pageNum"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @current-change="handlePageChange"
          @size-change="loadRecords"
        />
      </div>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.blockchain-cert {
  .card-title {
    font-size: 15px;
    font-weight: 600;
    color: #303133;
  }

  .top-row {
    margin-bottom: 16px;

    .el-col {
      margin-bottom: 16px;
    }
  }

  .cert-btn {
    margin-top: 12px;
  }

  .cert-result {
    margin-top: 16px;
    padding: 16px;
    background: rgba(233, 247, 247, .62);
    border: 1px solid rgba(145, 185, 190, .22);
    border-radius: 10px;

    .result-item {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 12px;

      &:last-child {
        margin-bottom: 0;
      }

      .item-label {
        flex-shrink: 0;
        width: 140px;
        font-size: 13px;
        font-weight: 600;
        color: #909399;
      }

      .block-index {
        font-weight: 600;
        color: #167b81;
      }
    }
  }

  .hash-line {
    display: flex;
    align-items: center;
    gap: 4px;
    min-width: 0;

    .hash-text {
      font-family: Consolas, Monaco, 'Courier New', monospace;
      font-size: 13px;
      color: #606266;
      word-break: break-all;
    }
  }

  .verify-result {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 16px;
    padding: 14px 16px;
    border-radius: 4px;
    font-size: 15px;
    font-weight: 600;

    &.success {
      color: #67c23a;
      background-color: rgba(#67c23a, 0.1);
    }

    &.fail {
      color: #f56c6c;
      background-color: rgba(#f56c6c, 0.1);
    }
  }

  .pagination {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
  }
}
</style>
