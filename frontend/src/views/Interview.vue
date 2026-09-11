<template>
  <div class="interview-page">
    <div class="page-header">
      <h1>模拟面试</h1>
      <p class="subtitle">可选查询目标公司信息，并根据岗位 JD 与简历生成针对性面试题</p>
    </div>

    <div class="steps-indicator">
      <div class="step-item" :class="{ active: true }">
        <span class="step-badge">1</span>
        <span>公司调研</span>
      </div>
      <div class="step-line" />
      <div class="step-item" :class="{ active: jd.ready && resume.ready }">
        <span class="step-badge">2</span>
        <span>生成题目</span>
      </div>
      <div class="step-line" />
      <div class="step-item" :class="{ active: questions.length > 0 }">
        <span class="step-badge">3</span>
        <span>查看题目</span>
      </div>
    </div>

    <div class="card section">
      <div class="card-header">
        <span class="step-badge">1</span>
        <div>
          <h3>公司信息查询</h3>
          <p class="hint section-hint">可选步骤，用于面试前了解目标公司的行业、业务与技术栈</p>
        </div>
      </div>

      <div class="form-row">
        <label class="field">
          <span class="field-label">公司名称</span>
          <input
            v-model="companyName"
            type="text"
            class="text-input"
            placeholder="如：阿里巴巴"
            @input="onCompanyInputChange"
          />
        </label>
        <label class="field">
          <span class="field-label">官网（可选）</span>
          <input
            v-model="officialWebsite"
            type="url"
            class="text-input"
            placeholder="https://www.example.com"
            @input="onCompanyInputChange"
          />
        </label>
      </div>

      <button
        class="btn btn-secondary"
        :disabled="!canSearchCompany || searching"
        @click="searchCompany"
      >
        {{ searching ? `正在检索公司信息... (${searchElapsed}s)` : '搜索公司信息' }}
      </button>
      <p v-if="searching" class="hint waiting-hint">正在联网检索并整理公司信息，通常需要 15–40 秒</p>
      <p v-if="searchError" class="error">{{ searchError }}</p>
      <p v-if="profileWarning && !searchError" class="warning">{{ profileWarning }}</p>
      <p v-if="fromCache" class="muted cache-hint">（来自缓存）</p>

      <CompanyProfile v-if="companyProfile" :profile="companyProfile" />
    </div>

    <div class="card section">
      <div class="card-header">
        <span class="step-badge">2</span>
        <div>
          <h3>面试题生成</h3>
          <p class="hint section-hint">上传或粘贴 JD 与简历，选择题型与数量后生成面试题</p>
        </div>
      </div>

      <div class="grid-2">
        <div class="card inner-card">
          <div class="inner-header">
            <span class="inner-icon">📋</span>
            <h3>岗位描述（JD）*</h3>
          </div>
          <FileUpload text-placeholder="请粘贴 JD，至少30字" @update="onJd" />
        </div>
        <div class="card inner-card">
          <div class="inner-header">
            <span class="inner-icon">📄</span>
            <h3>简历 *</h3>
          </div>
          <FileUpload :min-chars="50" text-placeholder="请粘贴简历，至少50字" @update="onResume" />
        </div>
      </div>

      <div class="card inner-card">
        <div class="inner-header">
          <span class="inner-icon">⚙️</span>
          <h3>题型与数量</h3>
        </div>
        <p v-if="companyProfile" class="hint company-hint">
          已检索公司信息，「公司业务题」将结合 {{ companyProfile.company_name || companyName }} 的业务背景生成
        </p>
        <div class="type-list">
          <div v-for="item in questionTypes" :key="item.key" class="type-row">
            <label class="type-label">
              <input v-model="item.enabled" type="checkbox" class="type-checkbox" />
              {{ item.label }}
            </label>
            <input
              v-model.number="item.count"
              type="number"
              min="1"
              max="20"
              class="count-input"
              :disabled="!item.enabled"
            />
            <span class="muted">道</span>
          </div>
        </div>
      </div>

      <div class="action-bar">
        <button class="btn" :disabled="!canGenerate || generating" @click="generateQuestions">
          {{ generating ? `正在生成面试题... (${generateElapsed}s)` : '生成面试题' }}
        </button>
        <p v-if="generating" class="hint waiting-hint">AI 生成中，请耐心等待（通常需要 20–60 秒）</p>
      </div>
      <p v-if="generateError" class="error">{{ generateError }}</p>
    </div>

    <div v-if="questions.length" class="card questions-card">
      <div class="card-header">
        <span class="step-badge">3</span>
        <h3>面试题目（{{ questions.length }} 道）</h3>
      </div>
      <details v-for="(q, idx) in questions" :key="q.id" class="question">
        <summary>
          <span class="q-num">{{ idx + 1 }}</span>
          <span class="badge badge-medium">{{ q.type }}</span>
          <span v-if="q.difficulty" class="badge badge-light">{{ q.difficulty }}</span>
          <span class="q-text">{{ q.question }}</span>
        </summary>
        <div class="question-body">
          <p v-if="q.focus"><strong>考察点：</strong>{{ q.focus }}</p>
          <p v-if="q.thinking"><strong>思路：</strong>{{ q.thinking }}</p>
          <p v-if="q.reference_answer"><strong>参考答案：</strong>{{ q.reference_answer }}</p>
          <p v-if="q.pitfalls?.length"><strong>误区：</strong>{{ q.pitfalls.join('；') }}</p>
          <p v-if="q.follow_ups?.length"><strong>追问：</strong>{{ q.follow_ups.join('；') }}</p>
        </div>
      </details>
    </div>
  </div>
</template>

<script setup>
import { computed, onUnmounted, ref } from 'vue'
import FileUpload from '../components/FileUpload.vue'
import CompanyProfile from '../components/CompanyProfile.vue'
import { generateInterview, researchCompany } from '../api'

const questionTypes = ref([
  { key: '技术题', label: '技术题', enabled: true, count: 3 },
  { key: '项目题', label: '项目题', enabled: true, count: 3 },
  { key: '行为题', label: '行为题', enabled: true, count: 2 },
  { key: 'HR/综合题', label: 'HR/综合题', enabled: false, count: 2 },
  { key: '公司业务题', label: '公司业务题', enabled: false, count: 2 },
])

const companyName = ref('')
const officialWebsite = ref('')
const searching = ref(false)
const searchError = ref('')
const profileWarning = ref('')
const searchElapsed = ref(0)
const companyProfile = ref(null)
const fromCache = ref(false)
const searchedName = ref('')
const searchedWebsite = ref('')

const jd = ref({})
const resume = ref({})
const generating = ref(false)
const generateError = ref('')
const generateElapsed = ref(0)
const questions = ref([])

let searchTimer = null
let generateTimer = null

function startElapsedTimer(target) {
  target.value = 0
  return setInterval(() => { target.value += 1 }, 1000)
}

function stopElapsedTimer(timerRef) {
  if (timerRef) clearInterval(timerRef)
}

onUnmounted(() => {
  stopElapsedTimer(searchTimer)
  stopElapsedTimer(generateTimer)
})

const canSearchCompany = computed(() => companyName.value.trim().length >= 2)

const canGenerate = computed(() => {
  const hasMaterials = jd.value.ready && resume.value.ready
  const hasTypes = questionTypes.value.some((t) => t.enabled && t.count >= 1)
  return hasMaterials && hasTypes
})

function onCompanyInputChange() {
  if (!companyProfile.value) return
  const nameChanged = companyName.value.trim() !== searchedName.value
  const siteChanged = officialWebsite.value.trim() !== searchedWebsite.value
  if (nameChanged || siteChanged) {
    companyProfile.value = null
    fromCache.value = false
  }
}

function onJd(data) { jd.value = data }
function onResume(data) { resume.value = data }

function isProfileEmpty(profile) {
  if (!profile) return true
  const p = profile.profile || {}
  for (const key of ['summary', 'industry', 'business']) {
    const field = p[key]
    if (!field) continue
    if (typeof field === 'string' && field.trim()) return false
    if (field?.value && String(field.value).trim()) return false
  }
  return true
}

function profileWarningMessage(profile) {
  if (!profile) return ''
  if (profile.low_confidence || profile.partial_result) {
    return '公开检索结果有限，以下信息置信度较低，建议填写官网后重试或直接继续生成面试题。'
  }
  if (!(profile.sources || []).length) {
    return '未找到可追溯的公开来源，以下信息仅供参考。'
  }
  return ''
}

async function searchCompany() {
  searching.value = true
  searchError.value = ''
  profileWarning.value = ''
  companyProfile.value = null
  fromCache.value = false
  searchTimer = startElapsedTimer(searchElapsed)
  try {
    const data = await researchCompany({
      company_name: companyName.value.trim(),
      official_website: officialWebsite.value.trim(),
      force_refresh: true,
    })
    companyProfile.value = data.company_profile
    fromCache.value = !!data.from_cache
    searchedName.value = companyName.value.trim()
    searchedWebsite.value = officialWebsite.value.trim()
    if (isProfileEmpty(data.company_profile)) {
      profileWarning.value = profileWarningMessage(data.company_profile) ||
        '未能检索到详细公司信息，但已返回有限公开资料，可继续生成面试题。'
    } else {
      profileWarning.value = profileWarningMessage(data.company_profile)
    }
  } catch (e) {
    searchError.value = e.message
  } finally {
    stopElapsedTimer(searchTimer)
    searchTimer = null
    searching.value = false
  }
}

function buildQuestionConfig() {
  const config = {}
  for (const t of questionTypes.value) {
    if (t.enabled && t.count >= 1) {
      config[t.key] = Math.min(20, Math.max(1, Math.floor(t.count)))
    }
  }
  return config
}

async function generateQuestions() {
  generating.value = true
  generateError.value = ''
  questions.value = []
  generateTimer = startElapsedTimer(generateElapsed)
  try {
    const payload = {
      question_config: buildQuestionConfig(),
      jd_source: jd.value.source || 'text',
      jd_file_id: jd.value.file_id,
      jd_text: jd.value.source === 'text' ? jd.value.text : null,
      jd_file_name: jd.value.file_name || '',
      resume_source: resume.value.source || 'text',
      resume_file_id: resume.value.file_id,
      resume_text: resume.value.source === 'text' ? resume.value.text : null,
      resume_file_name: resume.value.file_name || '',
    }
    if (companyProfile.value) {
      payload.company_name = companyProfile.value.company_name || companyName.value.trim()
      payload.company_profile = companyProfile.value
    }
    const data = await generateInterview(payload)
    questions.value = data.questions || []
  } catch (e) {
    generateError.value = e.message
  } finally {
    stopElapsedTimer(generateTimer)
    generateTimer = null
    generating.value = false
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
  max-width: 60px;
}
.section { margin-bottom: 20px; }
.section-hint { margin: 4px 0 0; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field-label { font-size: 13px; color: var(--color-text); font-weight: 500; }
.text-input {
  padding: 10px 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 14px;
  width: 100%;
  background: var(--color-surface);
  transition: border-color 0.15s, box-shadow 0.15s;
}
.text-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.12);
}
.inner-card {
  box-shadow: none;
  border: 1px solid var(--color-border-light);
  background: #fafbfc;
  margin-bottom: 12px;
  padding: 20px;
}
.inner-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.inner-header h3 { margin: 0; }
.inner-icon { font-size: 18px; }
.cache-hint { margin-top: 8px; }
.company-hint { color: var(--color-primary); }
.type-list { display: flex; flex-direction: column; gap: 10px; }
.type-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: var(--color-surface);
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border-light);
}
.type-label { display: flex; align-items: center; gap: 8px; min-width: 140px; font-size: 14px; cursor: pointer; }
.type-checkbox { accent-color: var(--color-primary); width: 16px; height: 16px; }
.count-input {
  width: 72px;
  padding: 6px 10px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  text-align: center;
}
.count-input:disabled { background: #f1f5f9; cursor: not-allowed; }
.questions-card .card-header { margin-bottom: 16px; }
.question {
  margin: 10px 0;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  background: #fafbfc;
  overflow: hidden;
  transition: border-color 0.15s;
}
.question:hover { border-color: #c7d2fe; }
.question summary {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 14px 16px;
  cursor: pointer;
  list-style: none;
}
.question summary::-webkit-details-marker { display: none; }
.q-num {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}
.q-text { flex: 1; font-size: 14px; line-height: 1.5; }
.badge-light { background: #e2e8f0; color: #475569; margin-right: 4px; }
.question-body {
  padding: 0 16px 16px 50px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-text);
}
.question-body p { margin: 8px 0; }
.question-body strong { color: var(--color-primary-dark); }
@media (max-width: 768px) {
  .form-row { grid-template-columns: 1fr; }
  .steps-indicator { flex-wrap: wrap; }
  .step-line { display: none; }
  .question-body { padding-left: 16px; }
}
</style>
