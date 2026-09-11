<template>
  <div class="dims">
    <div v-for="d in dimensions" :key="d.id" class="dim-row" :class="{ 'dim-missing': d.missing_info }">
      <div class="dim-head">
        <span class="dim-name">{{ d.name }}</span>
        <span class="dim-meta">
          <span :class="badgeClass(d.level)">{{ d.level }}</span>
          <span v-if="d.missing_info" class="badge badge-missing">信息不足（简历未提供）</span>
          <strong class="dim-score">{{ d.score }}分</strong>
        </span>
      </div>
      <div class="bar-bg"><div class="bar" :style="barStyle(d.score)" /></div>
      <p class="score-reason">
        <span class="score-reason-label">给分原因：</span>{{ displayScoreReason(d) }}
      </p>
      <ul v-if="d.evidence?.length" class="evidence-list">
        <li v-for="(item, idx) in d.evidence" :key="idx">{{ item }}</li>
      </ul>
      <ul v-if="d.scoring_breakdown?.length" class="breakdown-list">
        <li
          v-for="(item, idx) in d.scoring_breakdown"
          :key="idx"
          :class="breakdownClass(item.type)"
        >
          {{ item.point }}
        </li>
      </ul>
      <p v-if="showAnalysis(d)" class="analysis">{{ d.analysis }}</p>
    </div>
  </div>
</template>

<script setup>
defineProps({ dimensions: { type: Array, default: () => [] } })

function badgeClass(level) {
  return {
    badge: true,
    'badge-high': level === '高',
    'badge-medium': level === '中',
    'badge-low': level === '低',
  }
}

function barStyle(score) {
  let color = '#ef4444'
  if (score >= 80) color = '#10b981'
  else if (score >= 50) color = '#f59e0b'
  return { width: `${score}%`, background: `linear-gradient(90deg, ${color}, ${color}cc)` }
}

function displayScoreReason(d) {
  return d.score_reason || d.analysis || '暂无给分说明'
}

function showAnalysis(d) {
  return d.analysis && d.analysis !== displayScoreReason(d)
}

function breakdownClass(type) {
  return {
    'breakdown-item': true,
    'breakdown-positive': type === 'positive',
    'breakdown-negative': type === 'negative',
    'breakdown-neutral': type === 'neutral' || !type,
  }
}
</script>

<style scoped>
.dims { display: flex; flex-direction: column; gap: 12px; }
.dim-row {
  padding: 16px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border-light);
  background: #fafbfc;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.dim-row:hover { border-color: #c7d2fe; box-shadow: var(--shadow-sm); }
.dim-missing { background: linear-gradient(135deg, #eef2ff, #f5f3ff); border-color: #c7d2fe; }
.dim-head { display: flex; justify-content: space-between; align-items: center; font-size: 14px; margin-bottom: 10px; gap: 12px; }
.dim-name { font-weight: 600; color: var(--color-text); }
.dim-meta { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.dim-score { font-size: 15px; color: var(--color-primary-dark); }
.bar-bg { height: 8px; background: #e2e8f0; border-radius: 4px; overflow: hidden; }
.bar { height: 100%; border-radius: 4px; transition: width 0.5s ease; }
.score-reason {
  font-size: 13px;
  color: var(--color-text);
  margin: 10px 0 0;
  line-height: 1.6;
  font-weight: 500;
}
.score-reason-label { color: var(--color-primary); font-weight: 600; }
.dim-missing .score-reason-label { color: #4338ca; }
.evidence-list {
  margin: 8px 0 0;
  padding-left: 18px;
  font-size: 12px;
  color: var(--color-text-muted);
}
.evidence-list li { margin: 3px 0; }
.breakdown-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 10px 0 0;
  padding: 0;
  list-style: none;
}
.breakdown-item {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid transparent;
}
.breakdown-positive { background: #ecfdf5; color: #047857; border-color: #a7f3d0; }
.breakdown-negative { background: #fef2f2; color: #b91c1c; border-color: #fecaca; }
.breakdown-neutral { background: #f1f5f9; color: #475569; border-color: #e2e8f0; }
.analysis { font-size: 13px; color: var(--color-text-muted); margin: 10px 0 0; line-height: 1.6; }
</style>
