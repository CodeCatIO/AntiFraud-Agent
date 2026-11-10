<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Stamp, Download, CopyDocument } from '@element-plus/icons-vue'
import { embedWatermark, extractWatermark } from '@/api/watermark'
import EmptyState from '@/components/EmptyState.vue'

const activeTab = ref('embed')

// ---------- 公共：图片上传校验 ----------
function validateImage(file) {
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

// ---------- Tab 1：水印嵌入 ----------
const embedFileList = ref([])
const embedImageUrl = ref('')
const watermarkText = ref('')
const embedLoading = ref(false)
const embedResultUrl = ref('')

const embedFile = ref(null)

function handleEmbedChange(file, files) {
  if (validateImage(file.raw)) {
    embedFileList.value = files.slice(-1)
    embedImageUrl.value = URL.createObjectURL(file.raw)
    embedFile.value = file.raw
    embedResultUrl.value = ''
  } else {
    embedFileList.value = []
  }
}

function handleEmbedRemove() {
  embedFileList.value = []
  embedImageUrl.value = ''
  embedFile.value = null
  embedResultUrl.value = ''
}

async function handleEmbed() {
  if (!embedFile.value) {
    ElMessage.warning('请先上传图片')
    return
  }
  if (!watermarkText.value.trim()) {
    ElMessage.warning('请输入水印文字')
    return
  }
  embedLoading.value = true
  try {
    // 接口未通前用 Mock 占位，接口通了以后替换为：
    // const formData = new FormData()
    // formData.append('file', embedFile.value)
    // formData.append('watermarkText', watermarkText.value)
    // const res = await embedWatermark(formData)
    // embedResultUrl.value = res.url // 后端返回带水印图片地址
    await new Promise((resolve) => setTimeout(resolve, 1000))
    // Mock：用原图 URL 占位展示效果
    embedResultUrl.value = embedImageUrl.value
    ElMessage.success('水印嵌入成功')
  } catch (e) {
    // 错误已由拦截器统一提示
  } finally {
    embedLoading.value = false
  }
}

function handleDownload() {
  if (!embedResultUrl.value) return
  const link = document.createElement('a')
  link.href = embedResultUrl.value
  link.download = `watermarked-${Date.now()}.png`
  link.click()
  ElMessage.success('开始下载')
}

// ---------- Tab 2：水印提取 ----------
const extractFileList = ref([])
const extractImageUrl = ref('')
const extractFile = ref(null)
const extractLoading = ref(false)
const extractText = ref('')
const extractFailed = ref(false)

function handleExtractChange(file, files) {
  if (validateImage(file.raw)) {
    extractFileList.value = files.slice(-1)
    extractImageUrl.value = URL.createObjectURL(file.raw)
    extractFile.value = file.raw
    extractText.value = ''
    extractFailed.value = false
  } else {
    extractFileList.value = []
  }
}

function handleExtractRemove() {
  extractFileList.value = []
  extractImageUrl.value = ''
  extractFile.value = null
  extractText.value = ''
  extractFailed.value = false
}

async function handleExtract() {
  if (!extractFile.value) {
    ElMessage.warning('请先上传带水印的图片')
    return
  }
  extractLoading.value = true
  extractText.value = ''
  extractFailed.value = false
  try {
    // 接口未通前用 Mock 占位，接口通了以后替换为：
    // const formData = new FormData()
    // formData.append('file', extractFile.value)
    // const res = await extractWatermark(formData)
    // extractText.value = res.watermarkText // 后端返回提取的水印文字
    await new Promise((resolve) => setTimeout(resolve, 1000))
    extractText.value = '反诈取证专用水印 20260507'
  } catch (e) {
    // 错误已由拦截器统一提示
    extractFailed.value = true
  } finally {
    extractLoading.value = false
  }
}

// ---------- 复制 ----------
async function handleCopy(text) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = text
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    ElMessage.success('已复制到剪贴板')
  }
}
</script>

<template>
  <div class="watermark-tool">
    <el-card shadow="hover">
      <el-tabs v-model="activeTab">
        <!-- Tab 1：水印嵌入 -->
        <el-tab-pane label="水印嵌入" name="embed">
          <el-row :gutter="16">
            <!-- 左：上传 + 参数 -->
            <el-col :xs="24" :md="12">
              <el-upload
                drag
                action="#"
                :auto-upload="false"
                :limit="1"
                :file-list="embedFileList"
                accept=".jpg,.jpeg,.png"
                :on-change="handleEmbedChange"
                :on-remove="handleEmbedRemove"
              >
                <el-icon class="upload-icon" :size="27"><Stamp /></el-icon>
                <div class="el-upload__text">将图片拖到此处，或<em>点击上传</em></div>
                <template #tip>
                  <div class="el-upload__tip">支持 jpg / png 格式，大小不超过 10MB</div>
                </template>
              </el-upload>

              <el-form label-position="top" class="embed-form" @submit.prevent>
                <el-form-item label="水印文字" required>
                  <el-input
                    v-model="watermarkText"
                    maxlength="50"
                    show-word-limit
                    placeholder="请输入要嵌入的水印文字（50 字以内）"
                  />
                </el-form-item>
              </el-form>

              <el-button
                type="primary"
                :icon="Stamp"
                :loading="embedLoading"
                @click="handleEmbed"
              >
                嵌入水印
              </el-button>
            </el-col>

            <!-- 右：预览对比 -->
            <el-col :xs="24" :md="12">
              <div v-if="embedImageUrl" class="preview-group">
                <div class="preview-item">
                  <div class="preview-label">原图</div>
                  <el-image
                    :src="embedImageUrl"
                    fit="contain"
                    :preview-src-list="[embedImageUrl]"
                    preview-teleported
                    hide-on-click-modal
                    class="preview-img"
                  />
                </div>
                <div v-if="embedResultUrl" class="preview-item">
                  <div class="preview-label">带水印</div>
                  <el-image
                    :src="embedResultUrl"
                    fit="contain"
                    :preview-src-list="[embedResultUrl]"
                    preview-teleported
                    hide-on-click-modal
                    class="preview-img"
                  />
                </div>
              </div>
              <EmptyState v-else :icon="Stamp" title="等待预览" description="上传图片后，可在这里对比水印效果。" />
            </el-col>
          </el-row>

          <!-- 下载 -->
          <div v-if="embedResultUrl" class="download-bar">
            <el-button type="success" :icon="Download" @click="handleDownload">
              下载带水印图片
            </el-button>
          </div>
        </el-tab-pane>

        <!-- Tab 2：水印提取 -->
        <el-tab-pane label="水印提取" name="extract">
          <el-row :gutter="16">
            <!-- 左：上传 -->
            <el-col :xs="24" :md="12">
              <el-upload
                drag
                action="#"
                :auto-upload="false"
                :limit="1"
                :file-list="extractFileList"
                accept=".jpg,.jpeg,.png"
                :on-change="handleExtractChange"
                :on-remove="handleExtractRemove"
              >
                <el-icon class="upload-icon" :size="27"><Stamp /></el-icon>
                <div class="el-upload__text">将带水印的图片拖到此处，或<em>点击上传</em></div>
                <template #tip>
                  <div class="el-upload__tip">支持 jpg / png 格式，大小不超过 10MB</div>
                </template>
              </el-upload>

              <el-button
                type="primary"
                :icon="Stamp"
                :loading="extractLoading"
                class="extract-btn"
                @click="handleExtract"
              >
                提取水印
              </el-button>
            </el-col>

            <!-- 右：预览 + 结果 -->
            <el-col :xs="24" :md="12">
              <div v-if="extractImageUrl" class="preview-item">
                <div class="preview-label">图片预览</div>
                <el-image
                  :src="extractImageUrl"
                  fit="contain"
                  :preview-src-list="[extractImageUrl]"
                  preview-teleported
                  hide-on-click-modal
                  class="preview-img"
                />
              </div>
              <EmptyState v-else :icon="Stamp" title="等待图片" description="上传带水印的图片后，即可尝试提取。" />

              <!-- 提取成功 -->
              <div v-if="extractText" class="extract-result success">
                <div class="result-label">提取出的水印文字</div>
                <div class="extract-text">{{ extractText }}</div>
                <el-button :icon="CopyDocument" size="small" @click="handleCopy(extractText)">
                  复制
                </el-button>
              </div>

              <!-- 提取失败 -->
              <div v-else-if="extractFailed" class="extract-result fail">
                <div class="result-label">提取失败</div>
                <div class="fail-text">未能从图片中提取到水印，请确认图片包含有效水印</div>
              </div>
            </el-col>
          </el-row>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.watermark-tool {
  .upload-icon {
    width: 56px;
    height: 56px;
    margin-bottom: 10px;
    border: 1px solid rgba(255, 255, 255, .9);
    border-radius: 16px;
    background: linear-gradient(145deg, rgba(218, 244, 242, .95), rgba(255, 255, 255, .57));
    box-shadow: 0 8px 20px rgba(32, 110, 120, .1);
    color: #167b81;
  }

  .embed-form {
    margin-top: 16px;
  }

  .extract-btn {
    margin-top: 16px;
  }

  .preview-group {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .preview-item {
    .preview-label {
      font-size: 13px;
      font-weight: 600;
      color: #909399;
      margin-bottom: 8px;
    }

    .preview-img {
      width: 100%;
      height: 220px;
      border-radius: 10px;
      border: 1px solid rgba(145, 185, 190, .3);
      cursor: pointer;
    }
  }

  .download-bar {
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid #e6e8eb;
  }

  .extract-result {
    margin-top: 16px;
    padding: 16px;
    border-radius: 10px;
    text-align: center;

    .result-label {
      font-size: 13px;
      font-weight: 600;
      color: #909399;
      margin-bottom: 12px;
    }

    &.success {
      background-color: rgba(#67c23a, 0.08);

      .extract-text {
        font-size: 22px;
        font-weight: 700;
        color: #303133;
        margin-bottom: 16px;
        word-break: break-all;
      }
    }

    &.fail {
      background-color: rgba(#f56c6c, 0.08);

      .fail-text {
        font-size: 14px;
        color: #909399;
        line-height: 1.6;
      }
    }
  }
}
</style>
