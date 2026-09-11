<template>
  <div class="home">
    <section class="hero">
      <div class="hero-content">
        <h1 class="hero-title">智能求职助手</h1>
        <p class="hero-subtitle">基于大模型的人岗匹配与面试题生成工具，助你精准定位优势、高效备战面试</p>
        <div v-if="health" class="hero-status">
          <span class="status-dot" />
          API 运行正常 · Mock LLM：{{ health.mock_llm ? '是' : '否' }}
        </div>
      </div>
    </section>

    <section class="features">
      <router-link to="/match" class="feature-card feature-match">
        <div class="feature-icon">🎯</div>
        <div class="feature-body">
          <h2>人岗匹配分析</h2>
          <p>8 维度智能匹配，环形进度条与雷达图可视化，个性化优化建议</p>
          <span class="feature-cta">开始分析 →</span>
        </div>
      </router-link>
      <router-link to="/interview" class="feature-card feature-interview">
        <div class="feature-icon">💼</div>
        <div class="feature-body">
          <h2>模拟面试</h2>
          <p>公司信息检索 + 根据 JD 与简历按题型生成面试题与参考答案</p>
          <span class="feature-cta">开始准备 →</span>
        </div>
      </router-link>
    </section>

    <section class="highlights">
      <div class="highlight-item">
        <span class="highlight-num">8</span>
        <span class="highlight-label">维度评估</span>
      </div>
      <div class="highlight-item">
        <span class="highlight-num">5+</span>
        <span class="highlight-label">题型覆盖</span>
      </div>
      <div class="highlight-item">
        <span class="highlight-num">AI</span>
        <span class="highlight-label">智能分析</span>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getHealth } from '../api'

const health = ref(null)

onMounted(async () => {
  try { health.value = await getHealth() } catch {}
})
</script>

<style scoped>
.hero {
  text-align: center;
  padding: 40px 24px 48px;
  margin-bottom: 8px;
}
.hero-title {
  font-size: 2.25rem;
  font-weight: 800;
  background: linear-gradient(135deg, #312e81 0%, #4f46e5 50%, #0ea5e9 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 12px;
  letter-spacing: -0.03em;
}
.hero-subtitle {
  font-size: 16px;
  color: var(--color-text-muted);
  max-width: 520px;
  margin: 0 auto 16px;
  line-height: 1.7;
}
.hero-status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.2);
  border-radius: 999px;
  font-size: 13px;
  color: #047857;
  font-weight: 500;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-success);
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.features {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 32px;
}
.feature-card {
  display: flex;
  gap: 20px;
  padding: 28px;
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-light);
  box-shadow: var(--shadow-card);
  text-decoration: none;
  color: inherit;
  transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
  position: relative;
  overflow: hidden;
}
.feature-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
}
.feature-match::before { background: linear-gradient(90deg, #4f46e5, #818cf8); }
.feature-interview::before { background: linear-gradient(90deg, #0ea5e9, #38bdf8); }
.feature-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
  border-color: transparent;
}
.feature-icon {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  flex-shrink: 0;
}
.feature-match .feature-icon { background: linear-gradient(135deg, #eef2ff, #e0e7ff); }
.feature-interview .feature-icon { background: linear-gradient(135deg, #e0f2fe, #bae6fd); }
.feature-body h2 {
  font-size: 1.15rem;
  font-weight: 700;
  margin-bottom: 8px;
  color: var(--color-text);
}
.feature-body p {
  font-size: 14px;
  color: var(--color-text-muted);
  margin: 0 0 14px;
  line-height: 1.6;
}
.feature-cta {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-primary);
}
.feature-interview .feature-cta { color: #0284c7; }

.highlights {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.highlight-item {
  text-align: center;
  padding: 20px;
  background: rgba(255, 255, 255, 0.7);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-light);
}
.highlight-num {
  display: block;
  font-size: 1.5rem;
  font-weight: 800;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 4px;
}
.highlight-label {
  font-size: 13px;
  color: var(--color-text-muted);
  font-weight: 500;
}

@media (max-width: 768px) {
  .hero-title { font-size: 1.75rem; }
  .features { grid-template-columns: 1fr; }
  .feature-card { flex-direction: column; text-align: center; }
  .highlights { grid-template-columns: 1fr; }
}
</style>
