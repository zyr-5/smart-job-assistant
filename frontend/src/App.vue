<template>
  <div id="app">
    <div v-if="health?.mock_llm" class="mock-banner">
      <div class="container mock-banner-inner">
        当前为演示模式，分数为模拟数据。配置 DEEPSEEK_API_KEY 后可获得真实评分
      </div>
    </div>
    <header class="header">
      <div class="container header-inner">
        <router-link to="/" class="logo">
          <span class="logo-icon">✦</span>
          <span>智能求职助手</span>
        </router-link>
        <nav>
          <router-link to="/match">
            <span class="nav-icon">◎</span>
            人岗匹配
          </router-link>
          <router-link to="/interview">
            <span class="nav-icon">◈</span>
            模拟面试
          </router-link>
        </nav>
      </div>
    </header>
    <main class="container main-content">
      <router-view />
    </main>
    <footer class="footer">
      <div class="container footer-inner">
        <span>智能求职助手 · 基于大模型的人岗匹配与面试准备工具</span>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getHealth } from './api'

const health = ref(null)

onMounted(async () => {
  try { health.value = await getHealth() } catch {}
})
</script>

<style scoped>
.header {
  background: linear-gradient(135deg, #312e81 0%, #4f46e5 50%, #6366f1 100%);
  border-bottom: none;
  box-shadow: 0 4px 20px rgba(79, 70, 229, 0.25);
  position: sticky;
  top: 0;
  z-index: 100;
}
.header-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 14px;
  padding-bottom: 14px;
}
.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 700;
  color: #fff;
  text-decoration: none;
  letter-spacing: -0.01em;
}
.logo:hover { color: #e0e7ff; }
.logo-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 8px;
  font-size: 16px;
}
nav { display: flex; gap: 8px; }
nav a {
  display: flex;
  align-items: center;
  gap: 6px;
  color: rgba(255, 255, 255, 0.85);
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
  padding: 8px 16px;
  border-radius: 8px;
  transition: background 0.15s, color 0.15s;
}
nav a:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  text-decoration: none;
}
nav a.router-link-active {
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
  font-weight: 600;
}
.nav-icon { font-size: 12px; opacity: 0.8; }
.main-content { min-height: calc(100vh - 140px); padding-top: 32px; padding-bottom: 48px; }
.footer {
  border-top: 1px solid var(--color-border);
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(8px);
}
.footer-inner {
  padding-top: 16px;
  padding-bottom: 16px;
  text-align: center;
  font-size: 12px;
  color: var(--color-text-muted);
}
</style>
