<template>
  <div class="file-upload">
    <div class="tabs">
      <button :class="['tab', mode === 'file' && 'active']" @click="mode = 'file'">文件</button>
      <button :class="['tab', mode === 'text' && 'active']" @click="mode = 'text'">文本</button>
    </div>

    <div v-if="mode === 'file'">
      <div
        class="dropzone"
        :class="{ dragging }"
        @dragover.prevent="dragging = true"
        @dragleave.prevent="dragging = false"
        @drop.prevent="onDrop"
        @click="triggerFile"
      >
        <div class="dropzone-icon">📁</div>
        <p class="dropzone-title">拖拽文件到此处，或点击上传</p>
        <p class="muted">支持 PDF、DOCX、TXT，最大 10MB</p>
        <input ref="fileInput" type="file" accept=".pdf,.docx,.txt" hidden @change="onFileChange" />
      </div>
      <div v-if="fileName" class="file-info">
        <span class="file-badge">✓</span>
        <span>已选：{{ fileName }}</span>
        <button class="link-btn" @click="clearFile">移除</button>
      </div>
      <div v-if="preview" class="preview">
        <details open>
          <summary>解析预览（{{ charCount }} 字，自动可用）</summary>
          <pre>{{ preview.slice(0, 500) }}{{ preview.length > 500 ? '...' : '' }}</pre>
        </details>
      </div>
    </div>

    <div v-else>
      <textarea v-model="textValue" :placeholder="textPlaceholder" rows="8" />
      <p class="muted char-count">{{ textValue.length }} 字</p>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { uploadParse } from '../api'

const props = defineProps({
  textPlaceholder: { type: String, default: '请粘贴文本...' },
  minChars: { type: Number, default: 30 },
})
const emit = defineEmits(['update'])

const mode = ref('file')
const dragging = ref(false)
const fileInput = ref(null)
const fileName = ref('')
const fileId = ref('')
const preview = ref('')
const charCount = ref(0)
const textValue = ref('')
const error = ref('')

function emitUpdate() {
  emit('update', {
    source: mode.value,
    file_id: mode.value === 'file' ? fileId.value : null,
    file_name: fileName.value,
    text: mode.value === 'text' ? textValue.value : preview.value,
    ready: mode.value === 'file' ? !!fileId.value : textValue.value.length >= props.minChars,
  })
}

watch([mode, textValue], () => emitUpdate())

async function handleFile(file) {
  error.value = ''
  try {
    const data = await uploadParse(file)
    fileName.value = data.file_name
    fileId.value = data.file_id
    preview.value = data.text
    charCount.value = data.char_count
    emitUpdate()
  } catch (e) {
    error.value = e.message
    clearFile()
  }
}

function onDrop(e) {
  dragging.value = false
  const file = e.dataTransfer.files[0]
  if (file) handleFile(file)
}

function onFileChange(e) {
  const file = e.target.files[0]
  if (file) handleFile(file)
}

function triggerFile() {
  fileInput.value?.click()
}

function clearFile() {
  fileName.value = ''
  fileId.value = ''
  preview.value = ''
  charCount.value = 0
  if (fileInput.value) fileInput.value.value = ''
  emitUpdate()
}

defineExpose({ mode, fileId, fileName, textValue, preview })
</script>

<style scoped>
.dropzone {
  border: 2px dashed #cbd5e1;
  border-radius: var(--radius-md);
  padding: 36px 24px;
  text-align: center;
  cursor: pointer;
  background: linear-gradient(135deg, #f8fafc, #f1f5f9);
  transition: all 0.2s;
}
.dropzone.dragging,
.dropzone:hover {
  border-color: var(--color-primary);
  background: linear-gradient(135deg, #eef2ff, #e0e7ff);
  transform: scale(1.01);
}
.dropzone-icon { font-size: 32px; margin-bottom: 8px; }
.dropzone-title { font-size: 14px; font-weight: 500; color: var(--color-text); margin: 0 0 4px; }
.file-info {
  margin-top: 12px;
  display: flex;
  gap: 10px;
  align-items: center;
  font-size: 14px;
  padding: 10px 14px;
  background: #ecfdf5;
  border-radius: var(--radius-sm);
  border: 1px solid #a7f3d0;
  color: #047857;
}
.file-badge {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #10b981;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
}
.link-btn {
  background: none;
  border: none;
  color: var(--color-danger);
  cursor: pointer;
  font-size: 13px;
  margin-left: auto;
  font-weight: 500;
}
.link-btn:hover { text-decoration: underline; }
.preview { margin-top: 12px; }
.preview summary {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-muted);
  cursor: pointer;
  margin-bottom: 6px;
}
.preview pre {
  background: #f1f5f9;
  padding: 12px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  white-space: pre-wrap;
  max-height: 160px;
  overflow: auto;
  border: 1px solid var(--color-border-light);
  line-height: 1.5;
}
textarea {
  width: 100%;
  padding: 12px 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 14px;
  resize: vertical;
  line-height: 1.6;
  transition: border-color 0.15s, box-shadow 0.15s;
  font-family: inherit;
}
textarea:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.12);
}
.char-count { margin-top: 6px; text-align: right; }
</style>
