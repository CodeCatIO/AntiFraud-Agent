<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Picture, Delete } from '@element-plus/icons-vue'
import { detectImage } from '@/api/detect'
import RiskResult from '@/components/RiskResult.vue'
import EmptyState from '@/components/EmptyState.vue'

const loading = ref(false)
const fileList = ref([])
const imageUrl = ref('')
const result = ref(null)

const currentFile = computed(() => fileList.value[0]?.raw || null)

// 技术指标配置
const metrics = computed(() => [
  {
    label: 'ELA 误差均值',
    value: result.value?.details?.ela_mean,
    desc: '误差水平分析（Error Level Analysis）均值，数值偏离正常范围说明图像局部经过二次压缩或编辑。',
  },
  {
    label: '边缘密度',
    value: result.value?.details?.edge_density,
    desc: '图像边缘密度反映纹理复杂度，异常偏高常见于合成、贴图等篡改操作。',
  },
  {
    label: '噪声水平',
    value: result.value?.details?.noise_level,
    desc: '传感器噪声一致性指标，拼接合成的图像各区域噪声分布往往不均匀。',
  },
  {
    label: '色彩分布异常度',
    value: result.value?.details?.color_anomaly,
    desc: '色彩直方图分布与自然图像的差异程度，异常说明色调可能被人为调整。',
  },
  {
    label: 'EXIF 完整性',
    value: result.value?.details?.exif_integrity,
    desc: '拍摄元数据（设备、时间等）完整性，缺失或被篡改提示图像来源可疑。',
  },
].filter((item) => item.value !== undefined && item.value !== null))

// 上传前校验：格式 + 大小
function handleBeforeUpload(file) {
  const isImage = file.type === 'image/jpeg' || file.type === 'image/png'
  if (!isImage && !/\.(jpe?g|png)$/i.test(file.name)) {
    ElMessage.error('仅支持 jpg / png 格式的图片')
    return false
  }
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.error('图片大小不能超过 10MB')
    return false
  }
  return true
}

function handleChange(file, files) {
  if (handleBeforeUpload(file.raw)) {
    fileList.value = files.slice(-1)
    imageUrl.value = URL.createObjectURL(file.raw)
    result.value = null
  } else {
    fileList.value = []
  }
}

function handleRemove() {
  fileList.value = []
  imageUrl.value = ''
  result.value = null
}

function handleClear() {
  handleRemove()
}

async function handleDetect() {
  if (!currentFile.value) {
    ElMessage.warning('请先上传图片')
    return
  }
  loading.value = true
  try {
    // 调用真实检测接口：POST /detect/image → Java 后端 → Flask AI 服务
    const formData = new FormData()
    formData.append('file', currentFile.value)
    const res = await detectImage(formData)

    // 后端返回 { recordId, riskScore, riskLevel, detail: {...AI结果} }
    // 映射为页面展示结构
    const d = res.detail || {}
    result.value = {
      risk_score: res.riskScore,
      risk_level: res.riskLevel,
      details: {
        analysis: d.detail,
        ela_mean: d.ela_score ?? d.elaScore,
        face_detected: d.face_detected ?? d.faceDetected,
        ocr_text: d.ocr_text ?? d.ocrText,
      },
    }
  } catch (e) {
    // 错误已由拦截器统一提示
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="image-detect">
    <div class="page-heading"><h1>图片检测</h1><p>上传图片，查看可疑编辑痕迹和模型给出的风险线索。</p></div>
    <el-row :gutter="16">
      <!-- 左侧：上传 + 预览 -->
      <el-col :xs="24" :md="12">
        <el-card shadow="hover">
          <template #header>
            <span class="card-title">图片上传</span>
          </template>

          <!-- 已选图片时隐藏拖拽区，节省空间 -->
          <el-upload
            v-if="!imageUrl"
            drag
            action="#"
            :auto-upload="false"
            :limit="1"
            :file-list="fileList"
            accept=".jpg,.jpeg,.png"
            :on-change="handleChange"
            :on-remove="handleRemove"
          >
            <el-icon class="upload-icon" :size="29"><Picture /></el-icon>
            <div class="el-upload__text">将图片拖到此处，或<em>点击上传</em></div>
            <template #tip>
              <div class="el-upload__tip">支持 jpg / png 格式，大小不超过 10MB</div>
            </template>
          </el-upload>

          <!-- 图片预览 -->
          <div v-if="imageUrl" class="preview">
            <el-image
              :src="imageUrl"
              fit="contain"
              :preview-src-list="[imageUrl]"
              preview-teleported
              hide-on-click-modal
              class="preview-img"
            />
            <div class="preview-actions">
              <el-button type="primary" :icon="Picture" :loading="loading" @click="handleDetect">
                开始检测
              </el-button>
              <el-button :icon="Delete" @click="handleClear">删除图片</el-button>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：结果区 -->
      <el-col :xs="24" :md="12">
        <el-card v-if="result" shadow="never" class="result-card">
          <RiskResult :level="result.risk_level" :score="result.risk_score">

          <div v-if="result.details?.ocr_text" class="block">
            <div class="block-label">OCR 识别文字</div>
            <p class="ocr-text">{{ result.details.ocr_text }}</p>
          </div>

          <div v-if="result.details?.analysis" class="block">
            <div class="block-label">详细分析</div>
            <p class="analysis-text">{{ result.details.analysis }}</p>
          </div>
          <p v-if="!result.details?.ocr_text && !result.details?.analysis && !metrics.length">当前结果未提供详细分析，请结合图片来源核实。</p>

          <!-- 技术指标折叠面板 -->
          <el-collapse v-if="metrics.length" class="metrics">
            <el-collapse-item v-for="metric in metrics" :key="metric.label" :title="metric.label">
              <div class="metric-value">检测值：{{ metric.value }}</div>
              <div class="metric-desc">{{ metric.desc }}</div>
            </el-collapse-item>
          </el-collapse>
          </RiskResult>
        </el-card>

        <el-card v-else shadow="hover" class="result-card empty-card">
          <EmptyState :icon="Picture" title="等待检测结果" description="上传图片并开始检测后，风险线索会显示在这里。" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.image-detect {
  max-width: 1440px;
  margin: 0 auto;
  .page-heading { margin-bottom: 24px; h1 { font-size: 27px; color: #172e43; } p { margin-top: 7px; color: #647887; } }
  // 左右两栏等高对齐
  :deep(.el-row) {
    align-items: stretch;
  }

  :deep(.el-col) {
    display: flex;
    flex-direction: column;
  }

  .el-card {
    width: 100%;
    flex: 1;
    display: flex;
    flex-direction: column;

    :deep(.el-card__body) {
      flex: 1;
      display: flex;
      flex-direction: column;
    }
  }

  .card-title {
    font-size: 15px;
    font-weight: 600;
    color: #303133;
  }

  .upload-icon {
    width: 58px;
    height: 58px;
    margin-bottom: 10px;
    border: 1px solid rgba(255, 255, 255, .9);
    border-radius: 17px;
    background: linear-gradient(145deg, rgba(218, 244, 242, .95), rgba(255, 255, 255, .57));
    box-shadow: 0 8px 20px rgba(32, 110, 120, .1);
    color: #167b81;
  }

  .preview {
    margin-top: 4px;
    flex: 1;
    display: flex;
    flex-direction: column;

    .preview-img {
      width: 100%;
      border-radius: 10px;
      border: 1px solid rgba(145, 185, 190, .3);
      cursor: pointer;
      overflow: hidden;

      // 小图按原始比例缩放显示，不浪费空间
      :deep(img) {
        width: 100%;
        height: auto;
        max-height: 320px;
        object-fit: contain;
        display: block;
      }
    }

    .preview-actions {
      margin-top: 12px;
    }
  }

  .result-card {
    .result-tags {
      display: flex;
      gap: 12px;
      margin-bottom: 14px;
    }

    .block-label {
      font-size: 13px;
      font-weight: 600;
      color: #909399;
      margin-bottom: 6px;
    }

    .score-block {
      margin-bottom: 14px;

      .confidence {
        margin-top: 6px;
        font-size: 13px;
        color: #909399;
      }
    }

    .block {
      margin-bottom: 14px;

      &:last-child {
        margin-bottom: 0;
      }
    }

    .ocr-text,
    .analysis-text {
      font-size: 14px;
      line-height: 1.7;
      color: #365466;
      background: rgba(233, 247, 247, .62);
      border: 1px solid rgba(145, 185, 190, .22);
      border-radius: 10px;
      padding: 10px 12px;
    }

    .metrics {
      border-top: 1px solid #e6e8eb;

      .metric-value {
        font-size: 14px;
        font-weight: 600;
        color: #303133;
        margin-bottom: 6px;
      }

      .metric-desc {
        font-size: 13px;
        line-height: 1.6;
        color: #909399;
      }
    }
  }

  .empty-card {
    :deep(.el-card__body) {
      justify-content: center;
    }

    :deep(.el-empty) {
      padding: 24px 0;
    }
  }
}
</style>
