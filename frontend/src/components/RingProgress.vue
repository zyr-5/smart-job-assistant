<template>
  <div class="ring-wrap">
    <svg :width="size" :height="size" :viewBox="`0 0 ${size} ${size}`">
      <defs>
        <linearGradient :id="gradientId" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" :stop-color="gradientStart" />
          <stop offset="100%" :stop-color="gradientEnd" />
        </linearGradient>
      </defs>
      <circle :cx="c" :cy="c" :r="r" fill="none" stroke="#e2e8f0" :stroke-width="stroke" />
      <circle
        :cx="c" :cy="c" :r="r" fill="none"
        :stroke="`url(#${gradientId})`" :stroke-width="stroke"
        :stroke-dasharray="circumference"
        :stroke-dashoffset="offset"
        stroke-linecap="round"
        :transform="`rotate(-90 ${c} ${c})`"
      />
    </svg>
    <div class="label">
      <div class="score" :style="{ color: scoreColor }">{{ score }}</div>
      <div class="text">{{ label }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  score: { type: Number, default: 0 },
  label: { type: String, default: '综合匹配' },
  size: { type: Number, default: 160 },
  stroke: { type: Number, default: 14 },
})

const gradientId = `ring-grad-${Math.random().toString(36).slice(2, 8)}`

const c = computed(() => props.size / 2)
const r = computed(() => (props.size - props.stroke) / 2)
const circumference = computed(() => 2 * Math.PI * r.value)
const offset = computed(() => circumference.value * (1 - props.score / 100))

const scoreColor = computed(() => {
  if (props.score >= 80) return '#059669'
  if (props.score >= 50) return '#d97706'
  return '#dc2626'
})

const gradientStart = computed(() => {
  if (props.score >= 80) return '#10b981'
  if (props.score >= 50) return '#f59e0b'
  return '#ef4444'
})

const gradientEnd = computed(() => {
  if (props.score >= 80) return '#34d399'
  if (props.score >= 50) return '#fbbf24'
  return '#f87171'
})
</script>

<style scoped>
.ring-wrap {
  position: relative;
  display: inline-block;
  padding: 8px;
  background: linear-gradient(135deg, #fafbfc, #f1f5f9);
  border-radius: 50%;
  box-shadow: var(--shadow-sm);
}
.label {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.score {
  font-size: 36px;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1;
}
.text {
  font-size: 13px;
  color: var(--color-text-muted);
  margin-top: 4px;
  font-weight: 500;
}
</style>
