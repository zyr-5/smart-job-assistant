<template>
  <div class="suggestions">
    <div v-for="(s, i) in suggestions" :key="i" class="suggestion-card">
      <div class="suggestion-header">
        <span class="suggestion-index">{{ i + 1 }}</span>
        <div class="suggestion-title-wrap">
          <span :class="badgeClass(s.priority)">{{ s.priority }}优先级</span>
          <h4 class="suggestion-issue">{{ s.issue }}</h4>
        </div>
      </div>

      <div class="suggestion-body">
        <p class="suggestion-advice">{{ s.advice }}</p>

        <blockquote v-if="s.example" class="suggestion-example">
          <span class="example-label">改写示例</span>
          {{ s.example }}
        </blockquote>

        <ol v-if="s.action_steps?.length" class="action-steps">
          <li v-for="(step, j) in s.action_steps" :key="j">{{ step }}</li>
        </ol>

        <p v-if="s.expected_impact" class="expected-impact">
          <span class="impact-label">预期效果</span>
          {{ s.expected_impact }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  suggestions: { type: Array, default: () => [] },
})

function badgeClass(priority) {
  return {
    badge: true,
    'badge-high': priority === '高',
    'badge-medium': priority === '中',
    'badge-low': priority === '低',
  }
}
</script>

<style scoped>
.suggestions {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 12px;
}

.suggestion-card {
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--color-surface);
  transition: box-shadow 0.15s, border-color 0.15s;
}
.suggestion-card:hover {
  border-color: #c7d2fe;
  box-shadow: var(--shadow-sm);
}

.suggestion-header {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 16px 18px 0;
}
.suggestion-index {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}
.suggestion-title-wrap { flex: 1; }
.suggestion-issue {
  margin: 6px 0 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  line-height: 1.4;
}

.suggestion-body {
  padding: 12px 18px 18px 60px;
}

.suggestion-advice {
  margin: 0 0 12px;
  font-size: 14px;
  line-height: 1.7;
  color: #374151;
}

.suggestion-example {
  margin: 0 0 12px;
  padding: 12px 16px;
  border-left: 3px solid var(--color-primary);
  background: linear-gradient(135deg, #eef2ff, #f0f9ff);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  font-size: 13px;
  line-height: 1.6;
  color: #3730a3;
}

.example-label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--color-primary);
  margin-bottom: 4px;
}

.action-steps {
  margin: 0 0 12px;
  padding-left: 20px;
  font-size: 13px;
  line-height: 1.7;
  color: #475569;
}
.action-steps li { margin: 5px 0; }
.action-steps li::marker { color: var(--color-primary); font-weight: 600; }

.expected-impact {
  margin: 0;
  padding: 10px 14px;
  background: linear-gradient(135deg, #ecfdf5, #d1fae5);
  border-radius: var(--radius-sm);
  font-size: 13px;
  line-height: 1.5;
  color: #047857;
  border: 1px solid #a7f3d0;
}
.impact-label { font-weight: 600; margin-right: 6px; }
.impact-label::after { content: '：'; }

@media (max-width: 768px) {
  .suggestion-body { padding-left: 18px; }
}
</style>
