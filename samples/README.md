# 测试样例说明

本目录提供用于测试「智能求职助手」人岗匹配功能的简历与职位描述（JD）样例。

## 文件列表

| 文件 | 类型 | 说明 |
|------|------|------|
| `resume_backend.txt` | 简历 | Python 后端开发（张明远，4 年经验） |
| `resume_frontend.txt` | 简历 | 前端开发（李雨桐，3 年经验，Vue/React） |
| `jd_backend.txt` | JD | Python 后端岗位，与 `resume_backend.txt` 高度匹配 |
| `jd_frontend.txt` | JD | Vue 前端岗位，与 `resume_frontend.txt` 高度匹配 |
| `jd_mismatch.txt` | JD | Java 高级架构师，与 `resume_backend.txt` 故意不匹配 |

若存在同名 `.docx` 文件，内容与 `.txt` 一致，可用于测试 DOCX 上传解析。

## 推荐测试组合

### 高匹配（预期得分较高）

| 简历 | JD | 预期 |
|------|-----|------|
| `resume_backend.txt` | `jd_backend.txt` | 技能、经验、技术栈高度吻合 |
| `resume_frontend.txt` | `jd_frontend.txt` | Vue/TS/工程化要求对齐 |

### 低匹配（预期得分较低）

| 简历 | JD | 预期 |
|------|-----|------|
| `resume_backend.txt` | `jd_mismatch.txt` | 语言栈（Python vs Java）、职级、行业均不匹配 |
| `resume_backend.txt` | `jd_frontend.txt` | 前后端岗位错配 |
| `resume_frontend.txt` | `jd_backend.txt` | 前后端岗位错配 |

### 交叉测试（可选）

| 简历 | JD | 说明 |
|------|-----|------|
| `resume_frontend.txt` | `jd_mismatch.txt` | 前端 vs Java 架构师，同样应得低分 |

## 使用方式

### 方式一：Web 界面上传

1. 启动前后端服务（见项目根目录 [README.md](../README.md)）
2. 打开 http://localhost:5173 ，进入「人岗匹配」页面
3. 上传简历文件（`.txt` 或 `.docx`）和 JD 文件
4. 点击分析，查看匹配得分与详细报告

### 方式二：API 调用

```bash
# 1. 上传简历
curl -X POST http://localhost:8000/api/upload/parse \
  -F "file=@samples/resume_backend.txt"

# 2. 上传 JD（记下返回的 file_id）
curl -X POST http://localhost:8000/api/upload/parse \
  -F "file=@samples/jd_backend.txt"

# 3. 发起匹配分析（将 RESUME_ID、JD_ID 替换为实际值）
curl -X POST http://localhost:8000/api/match/analyze \
  -H "Content-Type: application/json" \
  -d "{\"resume_source\":\"file\",\"resume_file_id\":\"RESUME_ID\",\"jd_source\":\"file\",\"jd_file_id\":\"JD_ID\"}"
```

### 方式三：直接粘贴文本

在匹配页面选择「粘贴文本」，将 `.txt` 文件内容复制粘贴即可，无需上传。

## 样例人物设定（虚构）

- **张明远**：上海，Python 后端，FastAPI/MySQL/Redis，4 年经验
- **李雨桐**：深圳，前端，Vue 3/React，3 年经验

所有姓名、公司与联系方式均为虚构，仅用于本地测试。
