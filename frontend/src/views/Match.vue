<template>
  <div class="match-page">
    <div class="page-header">
      <h1>人岗匹配分析</h1>
      <p class="subtitle">上传简历与岗位描述，获取 8 维度智能匹配评分与优化建议</p>
    </div>

    <div class="steps-indicator">
      <div class="step-item active">
        <span class="step-badge">1</span>
        <span>上传材料</span>
      </div>
      <div class="step-line" />
      <div class="step-item" :class="{ active: result }">
        <span class="step-badge">2</span>
        <span>查看结果</span>
      </div>
    </div>

    <div class="grid-2">
      <div class="card input-card">
        <div class="card-header">
          <span class="icon icon-resume">📄</span>
          <h3>简历</h3>
        </div>
        <FileUpload ref="resumeRef" :min-chars="50" text-placeholder="请粘贴简历，至少50字" @update="onResume" />
      </div>
      <div class="card input-card">
        <div class="card-header">
          <span class="icon icon-jd">📋</span>
          <h3>岗位描述（JD）</h3>
        </div>
        <FileUpload ref="jdRef" text-placeholder="请粘贴JD，至少30字" @update="onJd" />
      </div>
    </div>

    <div class="action-bar">
      <button class="btn" :disabled="!canSubmit || loading" @click="submit">
        {{ loading ? `分析中... (${elapsed}s)` : '开始分析' }}
      </button>
      <p v-if="loading" class="hint waiting-hint">AI 分析中，请耐心等待（通常需要 20–60 秒）</p>
    </div>
    <p v-if="error" class="error">{{ error }}</p>

    <template v-if="result">
      <div class="section-divider" />

      <div class="card results-card">
        <div class="card-header">
          <span class="icon icon-result">📊</span>
          <h3>匹配分析结果</h3>
        </div>

        <div class="results-charts">
          <div class="ring-col">
            <RingProgress :score="result.overall_score" />
          </div>
          <div class="radar-col">
            <h3 class="radar-title">八维得分分布</h3>
            <RadarChart :dimensions="result.dimensions" />
          </div>
        </div>

        <div class="section-divider" />

        <div class="card-header" style="border-bottom: none; padding-bottom: 0;">
          <span class="icon icon-dims">📈</span>
          <h3>维度详情</h3>
        </div>
        <DimensionList :dimensions="result.dimensions" />

        <div class="section-divider" />

        <div class="card-header" style="border-bottom: none; padding-bottom: 0;">
          <span class="icon icon-suggest">💡</span>
          <h3>优化建议</h3>
        </div>
        <SuggestionList :suggestions="result.suggestions" />
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onUnmounted, ref } from 'vue'
import FileUpload from '../components/FileUpload.vue'
import RingProgress from '../components/RingProgress.vue'
import RadarChart from '../components/RadarChart.vue'
import DimensionList from '../components/DimensionList.vue'
import SuggestionList from '../components/SuggestionList.vue'
import { analyzeMatch } from '../api'

const resume = ref({})
const jd = ref({})
const loading = ref(false)
const error = ref('')
const result = ref(null)
const elapsed = ref(0)

let elapsedTimer = null

function startElapsedTimer() {
  elapsed.value = 0
  return setInterval(() => { elapsed.value += 1 }, 1000)
}

onUnmounted(() => {
  if (elapsedTimer) clearInterval(elapsedTimer)
})

const canSubmit = computed(() => resume.value.ready && jd.value.ready)

function onResume(data) { resume.value = data }
function onJd(data) { jd.value = data }

async function submit() {
  loading.value = true
  error.value = ''
  result.value = null
  elapsedTimer = startElapsedTimer()
  try {
    const payload = {
      resume_source: resume.value.source,
      resume_file_id: resume.value.file_id,
      resume_text: resume.value.source === 'text' ? resume.value.text : null,
      resume_file_name: resume.value.file_name || '',
      jd_source: jd.value.source,
      jd_file_id: jd.value.file_id,
      jd_text: jd.value.source === 'text' ? jd.value.text : null,
      jd_file_name: jd.value.file_name || '',
    }
    const data = await analyzeMatch(payload)
    result.value = data.result
  } catch (e) {
    error.value = e.message
  } finally {
    if (elapsedTimer) clearInterval(elapsedTimer)
    elapsedTimer = null
    loading.value = false
  }
}
</script>

<style scoped>
.steps-indicator {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 28px;
  padding: 16px 20px;
  background: rgba(255, 255, 255, 0.7);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-light);
}
.step-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: var(--color-text-muted);
  font-weight: 500;
}
.step-item.active { color: var(--color-text); }
.step-line {
  flex: 1;
  height: 2px;
  background: linear-gradient(90deg, var(--color-primary-light), var(--color-border));
  border-radius: 1px;
  max-width: 80px;
}
.input-card .icon-resume { background: linear-gradient(135deg, #eef2ff, #e0e7ff); }
.input-card .icon-jd { background: linear-gradient(135deg, #fef3c7, #fde68a); }
.results-card .icon-result { background: linear-gradient(135deg, #d1fae5, #a7f3d0); }
.results-card .icon-dims { background: linear-gradient(135deg, #e0f2fe, #bae6fd); }
.results-card .icon-suggest { background: linear-gradient(135deg, #fce7f3, #fbcfe8); }

.results-charts {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 32px;
  align-items: center;
  margin-bottom: 8px;
}
.ring-col { display: flex; justify-content: center; }
.radar-col { min-width: 0; }
.radar-title {
  margin: 0 0 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  text-align: center;
}
@media (max-width: 768px) {
  .results-charts { grid-template-columns: 1fr; }
  .steps-indicator { flex-wrap: wrap; }
  .step-line { display: none; }
}
</style>
