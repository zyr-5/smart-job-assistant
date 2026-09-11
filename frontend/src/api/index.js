import axios from 'axios'

const DEFAULT_TIMEOUT = 120000
const COMPANY_TIMEOUT = 300000
const INTERVIEW_TIMEOUT = 180000

function formatApiError(err) {
  if (err.code === 'ECONNABORTED' || /timeout/i.test(err.message || '')) {
    const url = err.config?.url || ''
    if (url.includes('/company/research')) {
      return '公司信息检索超时（网络搜索较慢）。请稍后重试，或填写官网地址后重试。'
    }
    if (url.includes('/interview/generate')) {
      return '面试题生成超时，AI 处理时间较长。请减少题型数量后重试，或稍后再试。'
    }
    if (url.includes('/match/analyze')) {
      return '匹配分析超时，AI 处理时间较长。请稍后重试。'
    }
    return '请求超时，服务器响应较慢。请稍后重试。'
  }
  const msg = err.response?.data?.detail || err.message || '网络错误'
  return typeof msg === 'string' ? msg : JSON.stringify(msg)
}

const api = axios.create({ baseURL: '/api', timeout: DEFAULT_TIMEOUT })

api.interceptors.response.use(
  (res) => {
    const body = res.data
    if (body.code !== 0) {
      return Promise.reject(new Error(body.message || '请求失败'))
    }
    return body.data
  },
  (err) => Promise.reject(new Error(formatApiError(err)))
)

function postWithTimeout(url, payload, timeout) {
  return api.post(url, payload, { timeout })
}

export async function uploadParse(file) {
  const form = new FormData()
  form.append('file', file)
  return api.post('/upload/parse', form)
}

export function analyzeMatch(payload) {
  return postWithTimeout('/match/analyze', payload, DEFAULT_TIMEOUT)
}

export function researchCompany(payload) {
  return postWithTimeout('/company/research', payload, COMPANY_TIMEOUT)
}

export function generateInterview(payload) {
  return postWithTimeout('/interview/generate', payload, INTERVIEW_TIMEOUT)
}

export function getHealth() {
  return api.get('/health')
}

export default api
