<template>
  <div class="radar-wrap">
    <v-chart class="radar-chart" :option="chartOption" autoresize />
    <p v-if="hasMissing" class="radar-hint">
      <span class="missing-dot" />虚线维度表示简历未提供该维度信息（计50分）
    </p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { RadarChart as EChartsRadar } from 'echarts/charts'
import { TooltipComponent, RadarComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, EChartsRadar, TooltipComponent, RadarComponent])

const SHORT_NAMES = {
  D1: '核心技能',
  D2: '工作经验',
  D3: '项目经历',
  D4: '行业匹配',
  D5: '学历资质',
  D6: '职责范围',
  D7: '软技能',
  D8: '职业发展',
}

const props = defineProps({
  dimensions: { type: Array, default: () => [] },
})

const orderedDims = computed(() => {
  const byId = Object.fromEntries(props.dimensions.map((d) => [d.id, d]))
  return ['D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8'].map(
    (id) => byId[id] || { id, name: SHORT_NAMES[id], score: 0, missing_info: false },
  )
})

const hasMissing = computed(() => orderedDims.value.some((d) => d.missing_info))

const chartOption = computed(() => {
  const dims = orderedDims.value
  const indicators = dims.map((d) => ({
    name: `${d.id} ${SHORT_NAMES[d.id] || d.name}`,
    max: 100,
    color: d.missing_info ? '#6366f1' : '#64748b',
  }))

  const scores = dims.map((d) => d.score ?? 0)

  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255,255,255,0.95)',
      borderColor: '#e2e8f0',
      textStyle: { color: '#1e293b', fontSize: 13 },
      formatter(params) {
        const lines = dims.map((d, i) => {
          const tag = d.missing_info ? ' <span style="color:#6366f1">(信息不足)</span>' : ''
          return `${d.id} ${SHORT_NAMES[d.id] || d.name}：${scores[i]}分${tag}`
        })
        return lines.join('<br/>')
      },
    },
    radar: {
      indicator: indicators,
      center: ['50%', '52%'],
      radius: '62%',
      splitNumber: 4,
      axisName: {
        fontSize: 11,
        fontWeight: 500,
        formatter: (name) => name,
      },
      splitLine: { lineStyle: { color: '#e2e8f0' } },
      splitArea: {
        show: true,
        areaStyle: { color: ['rgba(79,70,229,0.02)', 'rgba(79,70,229,0.05)'] },
      },
      axisLine: { lineStyle: { color: '#cbd5e1' } },
    },
    series: [
      {
        type: 'radar',
        symbol: 'circle',
        symbolSize: 7,
        data: [
          {
            value: scores,
            name: '维度得分',
            lineStyle: { color: '#4f46e5', width: 2.5 },
            areaStyle: { color: 'rgba(79, 70, 229, 0.15)' },
            itemStyle: {
              color: (params) => (dims[params.dimensionIndex]?.missing_info ? '#6366f1' : '#4f46e5'),
              borderColor: '#fff',
              borderWidth: 2,
            },
          },
        ],
      },
    ],
  }
})
</script>

<style scoped>
.radar-wrap {
  width: 100%;
  min-width: 0;
  padding: 8px;
  background: linear-gradient(135deg, #fafbfc, #f8fafc);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-light);
}
.radar-chart {
  width: 100%;
  height: 320px;
}
.radar-hint {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--color-text-muted);
  text-align: center;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}
.missing-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #6366f1;
}
</style>
