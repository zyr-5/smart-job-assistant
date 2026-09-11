<template>
  <div v-if="profile" class="company-profile">
    <div class="grid-2 profile-grid">
      <div v-for="(item, key) in fields" :key="key" class="field-card">
        <div class="field-header">
          <span class="field-icon">{{ fieldIcons[key] }}</span>
          <h4>{{ item.label }}
            <span :class="confClass(item.data?.confidence)">{{ confLabel(item.data?.confidence) }}</span>
          </h4>
        </div>
        <p v-if="key === 'tech_stack'">
          <span v-if="!item.data?.value?.length" class="muted">暂无可靠公开来源</span>
          <span v-else class="tech-tags">
            <span v-for="(t, i) in item.data.value" :key="i" class="tech-tag">{{ t }}</span>
          </span>
        </p>
        <p v-else class="field-value">{{ item.data?.value || '未知' }}</p>
        <div v-if="item.data?.sources?.length" class="sources">
          <a v-for="(s, i) in item.data.sources" :key="i" :href="s" target="_blank" class="source-link">来源{{ i + 1 }}</a>
        </div>
      </div>
    </div>

    <p class="disclaimer">{{ profile.disclaimer }}</p>

    <div class="sources-section">
      <h3>信息来源与溯源</h3>
      <div class="table-wrap">
        <table class="source-table">
          <thead>
            <tr><th>来源</th><th>搜索引擎</th><th>级别</th><th>类型</th><th>摘要</th></tr>
          </thead>
          <tbody>
            <tr v-for="(s, i) in profile.sources || []" :key="i">
              <td><a :href="s.url" target="_blank">{{ s.title || s.url }}</a></td>
              <td>{{ providerLabel(s.provider) }}</td>
              <td><span :class="tierClass(s.tier)">{{ s.tier }}</span></td>
              <td>{{ typeLabel(s.source_type) }}</td>
              <td class="snippet">{{ s.snippet }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ profile: Object })

const fieldIcons = {
  summary: '🏢',
  industry: '🏭',
  business: '💼',
  tech_stack: '⚙️',
}

const fields = computed(() => {
  const p = props.profile?.profile || {}
  return {
    summary: { label: '公司概览', data: normalizeField(p.summary) },
    industry: { label: '行业', data: normalizeField(p.industry) },
    business: { label: '主营业务', data: normalizeField(p.business) },
    tech_stack: { label: '技术栈', data: normalizeField(p.tech_stack, true) },
  }
})

function normalizeField(raw, isTechStack = false) {
  if (!raw) {
    return isTechStack
      ? { value: [], confidence: 'low' }
      : { value: null, confidence: 'low' }
  }
  if (typeof raw === 'string') {
    return { value: raw, confidence: 'low' }
  }
  if (isTechStack && raw.value == null) {
    return { ...raw, value: [] }
  }
  return raw
}

function confClass(c) {
  return { badge: true, 'badge-high': c === 'high', 'badge-medium': c === 'medium', 'badge-low': c === 'low' }
}
function confLabel(c) {
  return { high: '高', medium: '中', low: '低' }[c] || '低'
}
function tierClass(t) {
  return { badge: true, 'badge-high': t === 'P0', 'badge-medium': t === 'P1', 'badge-low': t === 'P2' }
}
function typeLabel(t) {
  return {
    official: '官网',
    news: '新闻资讯',
    recruitment: '招聘/JD',
    tech_blog: '技术博客',
    wiki: '百科',
    finance: '财报/融资',
    social: '社交媒体',
    other: '其他',
  }[t] || t
}
function providerLabel(p) {
  return { duckduckgo: 'DuckDuckGo', baidu: '百度', bing: 'Bing', unknown: '其他' }[p] || p || 'DuckDuckGo'
}
</script>

<style scoped>
.company-profile { margin-top: 20px; }
.profile-grid { gap: 14px; }
.field-card {
  background: linear-gradient(135deg, #fafbfc, #f8fafc);
  padding: 16px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border-light);
  transition: border-color 0.15s;
}
.field-card:hover { border-color: #c7d2fe; }
.field-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.field-icon { font-size: 18px; }
.field-card h4 {
  margin: 0;
  font-size: 14px;
  display: flex;
  gap: 8px;
  align-items: center;
  font-weight: 600;
}
.field-value { font-size: 14px; line-height: 1.6; color: var(--color-text); margin: 0; }
.tech-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.tech-tag {
  display: inline-block;
  padding: 3px 10px;
  background: #e0e7ff;
  color: #3730a3;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
}
.sources { margin-top: 10px; }
.source-link {
  font-size: 12px;
  margin-right: 10px;
  padding: 2px 8px;
  background: #f1f5f9;
  border-radius: 4px;
}
.disclaimer {
  font-size: 12px;
  color: var(--color-text-muted);
  margin: 16px 0;
  padding: 10px 14px;
  background: #f8fafc;
  border-radius: var(--radius-sm);
  border-left: 3px solid #e2e8f0;
}
.sources-section h3 { margin-bottom: 12px; }
.table-wrap { overflow-x: auto; border-radius: var(--radius-sm); border: 1px solid var(--color-border-light); }
.source-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.source-table th {
  background: #f8fafc;
  font-weight: 600;
  color: var(--color-text);
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
}
.source-table td {
  border-bottom: 1px solid var(--color-border-light);
  padding: 10px 12px;
  text-align: left;
}
.source-table tr:last-child td { border-bottom: none; }
.source-table tr:hover td { background: #fafbfc; }
.snippet { max-width: 300px; color: var(--color-text-muted); line-height: 1.5; }
</style>
