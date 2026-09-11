# 智能求职助手

基于 LLM 的求职辅助平台：**人岗匹配分析**、**公司信息检索**、**模拟面试题生成**。
前后端分离，后端 FastAPI + 前端 Vue3，线上单容器部署。

> 在线演示：_（部署完成后替换为 Render 地址）_
> 源码：https://github.com/zyr-5/smart-job-assistant

---

## 功能

| 模块 | 说明 |
|---|---|
| **人岗匹配** | 8 维度匹配引擎（等权平均汇总），LLM 以 JSON 结构化输出评分、逐维得分理由与可执行的简历优化建议 |
| **公司检索** | Bing / DuckDuckGo / Baidu 多引擎分级容错检索，返回结构化公司画像与来源可信度分级 |
| **模拟面试** | 按题型配置（技术/项目/行为/公司业务/HR）生成针对性面试题，含参考回答与追问建议 |
| **结果可视化** | ECharts 雷达图展示 8 维得分、环形进度展示总分、建议列表按优先级分组 |

## 技术栈

- **后端**：Python 3.12、FastAPI、Pydantic、httpx
- **前端**：Vue 3、Vite、ECharts、Axios
- **LLM**：DeepSeek（OpenAI 兼容客户端）
- **检索**：Bing / DuckDuckGo / Baidu，BeautifulSoup 解析
- **存储**：本地 JSON（公司信息缓存 + 分析历史）
- **文档解析**：python-docx、pypdf

## 工程要点

- **统一 LLM 调用层**：JSON 输出约束 + Pydantic 严格校验 + 失败重试与降级，避免模型返回不稳定导致接口 5xx
- **多引擎分级容错检索**：单一引擎失效自动切换下一个，配合并发抓取与 MD5 + TTL 缓存，检索耗时由约 40s 降至约 15s
- **离线可用**：未配置 API Key 时自动切换规则引擎 Mock 模式（关键词重合度 + 正则打分），无需 Key 也能完整演示
- **单端口部署**：生产环境由 `backend/serve.py` 同时提供前端静态资源与 `/api` 接口，无需 Nginx、无跨域配置
- **测试**：33 项 pytest 用例，覆盖匹配引擎、检索链路、配置解析与 API 集成

## 快速开始

### 1. 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env          # 可选：本地覆盖项（系统环境变量优先）
uvicorn app.main:app --reload --port 8000
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

### 3. 生产模式（单端口）

```bash
cd frontend && npm install && npm run build
cd ../backend && python serve.py --port 8000
```

访问 http://localhost:8000 即可，页面与接口同源。

### 4. Docker

```bash
docker build -t smart-job-assistant .
docker run -p 8000:8000 -e DEEPSEEK_API_KEY=sk-xxx -v jobdata:/data smart-job-assistant
```

## 测试

```bash
cd backend
pip install pytest pytest-cov
pytest -q --cov=app
```

## 环境变量

推荐将 `DEEPSEEK_API_KEY` 设置在**系统/用户环境变量**中（Windows：系统属性 → 环境变量）。启动后端或 `serve.py` 的终端必须能读到该变量；若仅在 IDE 里配置而未写入系统环境，需在同一终端会话中 `set DEEPSEEK_API_KEY=...` 后再启动。

**优先级**：进程环境变量（`os.environ`）> `backend/.env` > 默认值。

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | 空（无密钥时进入 Mock 模式） |
| `DEEPSEEK_BASE_URL` | API 地址 | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | 模型名 | `deepseek-chat` |
| `MOCK_LLM` | 无 Key 时为 `true` 则 Mock；**有 Key 时始终走真实 API** | `false` |
| `COMPANY_CACHE_TTL_DAYS` | 公司信息缓存天数 | `3` |
| `DATA_DIR` | 数据目录（缓存/历史/上传），容器部署时指向挂载卷 | 项目根 `data/` |

健康检查 `GET /api/health` 返回 `mock_llm: false` 表示已检测到 API Key 并将调用 DeepSeek。

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/upload/parse` | 上传并解析简历/JD（支持 pdf、docx、txt） |
| POST | `/api/match/analyze` | 8 维度人岗匹配分析 |
| POST | `/api/company/research` | 公司信息检索与结构化 |
| POST | `/api/interview/generate` | 生成模拟面试题 |
| GET | `/api/health` | 健康检查 |

## 测试样例

项目根目录 `samples/` 提供简历与 JD 测试文件（含高匹配与低匹配组合），详见 [samples/README.md](samples/README.md)。

## 部署

见根目录 `render.yaml`（Render Blueprint）与 `Dockerfile`。
