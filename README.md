# 智能求职助手

基于 PRD v1.3 的智能求职助手：人岗匹配分析、模拟面试生成。

## 技术栈

- 后端：Python + FastAPI
- 前端：Vue 3 + Vite
- 存储：本地 JSON（公司信息缓存）
- 搜索：DuckDuckGo（中文）
- LLM：DeepSeek（OpenAI 兼容客户端；未配置 API Key 时自动使用 Mock 模式）

## 快速开始

### 1. 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
copy .env.example .env   # 可选：本地覆盖项（系统环境变量优先）
uvicorn app.main:app --reload --port 8000
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

## 环境变量

推荐将 `DEEPSEEK_API_KEY` 设置在**系统/用户环境变量**中（Windows：系统属性 → 环境变量）。启动 `uvicorn` 的终端必须能读到该变量；若仅在 IDE 里配置而未写入系统环境，需在同一终端会话中 `set DEEPSEEK_API_KEY=...` 后再启动后端。

**优先级**：进程环境变量（`os.environ`）> `backend/.env` > 默认值。

| 变量 | 说明 | 默认值 |
|------|------|--------|
| DEEPSEEK_API_KEY | DeepSeek API 密钥 | 空（无密钥时进入 Mock） |
| DEEPSEEK_BASE_URL | API 地址 | `https://api.deepseek.com` |
| DEEPSEEK_MODEL | 模型名 | `deepseek-chat` |
| MOCK_LLM | 无 API Key 时为 `true` 则 Mock；**有 Key 时始终走真实 API** | `false` |
| COMPANY_CACHE_TTL_DAYS | 公司信息缓存天数 | `3` |

健康检查 `GET /api/health` 返回 `mock_llm: false` 表示已检测到 API Key 并将调用 DeepSeek。

## 测试样例

项目根目录 `samples/` 提供简历与 JD 测试文件（含高匹配与低匹配组合），详见 [samples/README.md](samples/README.md)。

## API

- `POST /api/upload/parse` - 文件解析
- `POST /api/match/analyze` - 人岗匹配
- `POST /api/company/research` - 公司检索
- `POST /api/interview/generate` - 模拟面试
