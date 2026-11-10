<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Microphone, VideoPlay, VideoPause, Delete } from '@element-plus/icons-vue'
import { detectVoice } from '@/api/detect'
import RiskResult from '@/components/RiskResult.vue'
import EmptyState from '@/components/EmptyState.vue'

const loading = ref(false)
const fileList = ref([])

// 仅展示真实的上传、检测和完成状态
const stepActive = ref(0)
const stepStatus = ref('process')

const result = ref(null)
const audioUrl = ref('')

// 当前选中文件
const currentFile = computed(() => fileList.value[0]?.raw || null)
const fileName = computed(() => fileList.value[0]?.name || '')
const fileSize = computed(() => {
  const raw = currentFile.value
  if (!raw) return ''
  const mb = raw.size / 1024 / 1024
  return mb >= 1 ? `${mb.toFixed(2)} MB` : `${(raw.size / 1024).toFixed(1)} KB`
})

// 上传前校验：格式 + 大小
function handleBeforeUpload(file) {
  const allowedTypes = ['audio/mpeg', 'audio/wav', 'audio/x-m4a', 'audio/mp4', 'audio/x-wav']
  const extOk = /\.(mp3|wav|m4a)$/i.test(file.name)
  if (!allowedTypes.includes(file.type) && !extOk) {
    ElMessage.error('仅支持 mp3、wav、m4a 格式的音频文件')
    return false
  }
  if (file.size > 20 * 1024 * 1024) {
    ElMessage.error('音频文件大小不能超过 20MB')
    return false
  }
  return true
}

// 选择文件后（手动上传模式）
function handleChange(file, files) {
  if (handleBeforeUpload(file.raw)) {
    fileList.value = files.slice(-1)
    stepActive.value = 1
    audioUrl.value = URL.createObjectURL(file.raw)
  } else {
    fileList.value = []
  }
}

function handleRemove() {
  resetAll()
}

// 音频播放控制
const playing = ref(false)
const audioRef = ref(null)

function togglePlay() {
  if (!audioRef.value) return
  if (playing.value) {
    audioRef.value.pause()
  } else {
    audioRef.value.play()
  }
}

function resetAll() {
  fileList.value = []
  audioUrl.value = ''
  playing.value = false
  result.value = null
  stepActive.value = 0
  stepStatus.value = 'process'
}

async function handleDetect() {
  if (!currentFile.value) {
    ElMessage.warning('请先上传音频文件')
    return
  }
  loading.value = true
  result.value = null
  try {
    stepActive.value = 2

    // 调用真实检测接口：POST /detect/voice → Java 后端 → Flask AI 服务
    const formData = new FormData()
    formData.append('file', currentFile.value)
    const res = await detectVoice(formData)

    // 后端返回 { recordId, riskScore, riskLevel, detail: {...AI结果} }
    // 映射为页面展示结构
    const d = res.detail || {}
    result.value = {
      risk_score: res.riskScore,
      risk_level: res.riskLevel,
      details: {
        transcript: d.transcript,
        analysis: d.detail,
      },
    }

    stepActive.value = 3
  } catch (e) {
    // 错误已由拦截器统一提示
    stepStatus.value = 'error'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="voice-detect">
    <div class="page-heading"><h1>语音检测</h1><p>上传通话或语音片段，查看文字转写与风险分析。</p></div>
    <!-- 上传区 -->
    <el-card shadow="hover">
      <template #header>
        <span class="card-title">语音上传</span>
      </template>

      <el-row :gutter="16">
        <el-col :xs="24" :md="12">
          <el-upload
            drag
            action="#"
            :auto-upload="false"
            :limit="1"
            :file-list="fileList"
            accept=".mp3,.wav,.m4a"
            :on-change="handleChange"
            :on-remove="handleRemove"
          >
            <el-icon class="upload-icon" :size="29"><Microphone /></el-icon>
            <div class="el-upload__text">将音频文件拖到此处，或<em>点击上传</em></div>
            <template #tip>
              <div class="el-upload__tip">支持 mp3 / wav / m4a 格式，大小不超过 20MB</div>
            </template>
          </el-upload>
        </el-col>

        <el-col :xs="24" :md="12">
          <!-- 已选文件信息 -->
          <div v-if="fileName" class="file-info">
            <div class="file-name">{{ fileName }}</div>
            <div class="file-size">{{ fileSize }}</div>

            <div class="audio-player">
              <el-button :icon="playing ? VideoPause : VideoPlay" circle @click="togglePlay" />
              <audio ref="audioRef" :src="audioUrl" @ended="playing = false" @play="playing = true" @pause="playing = false" />
            </div>

            <el-button type="primary" :icon="Microphone" :loading="loading" class="detect-btn" @click="handleDetect">
              开始检测
            </el-button>
          </div>

          <EmptyState v-else :icon="Microphone" title="等待音频" description="上传音频后，可在这里查看文件并开始检测。" />
        </el-col>
      </el-row>

      <!-- 步骤条 -->
      <el-steps :active="stepActive" :status="stepStatus" align-center class="steps">
        <el-step title="上传" />
        <el-step title="检测中" />
        <el-step title="完成" />
      </el-steps>
    </el-card>

    <!-- 结果区 -->
    <el-card v-if="result" shadow="never" class="result-card">
      <RiskResult :level="result.risk_level" :score="result.risk_score">
        <div v-if="result.details?.transcript" class="block"><div class="block-label">语音转文字</div><p class="transcript-text">{{ result.details.transcript }}</p></div>
        <div v-if="result.details?.analysis" class="block"><div class="block-label">详细分析</div><p class="analysis-text">{{ result.details.analysis }}</p></div>
        <p v-if="!result.details?.transcript && !result.details?.analysis">当前结果未提供详细分析，请结合实际情况核实。</p>
      </RiskResult>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.voice-detect {
  max-width: 1440px;
  margin: 0 auto;
  .page-heading { margin-bottom: 24px; h1 { font-size: 27px; color: #172e43; } p { margin-top: 7px; color: #647887; } }
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

  .file-info {
    padding: 12px 0;

    .file-name {
      font-size: 15px;
      font-weight: 600;
      color: #303133;
      word-break: break-all;
    }

    .file-size {
      margin-top: 4px;
      font-size: 13px;
      color: #909399;
    }

    .audio-player {
      display: flex;
      align-items: center;
      margin-top: 12px;
    }

    .detect-btn {
      margin-top: 16px;
    }
  }

  .steps {
    margin-top: 8px;
  }

  .result-card {
    margin-top: 16px;

    .result-tags {
      display: flex;
      gap: 12px;
      margin-bottom: 20px;
    }

    .block-label {
      font-size: 13px;
      font-weight: 600;
      color: #909399;
      margin-bottom: 8px;
    }

    .score-block {
      margin-bottom: 20px;

      .confidence {
        margin-top: 8px;
        font-size: 13px;
        color: #909399;
      }
    }

    .block {
      margin-bottom: 20px;

      &:last-child {
        margin-bottom: 0;
      }
    }

    .transcript-text,
    .analysis-text {
      font-size: 14px;
      line-height: 1.8;
      color: #365466;
      background: rgba(233, 247, 247, .62);
      border: 1px solid rgba(145, 185, 190, .22);
      border-radius: 10px;
      padding: 12px;
    }
  }
}
</style>
