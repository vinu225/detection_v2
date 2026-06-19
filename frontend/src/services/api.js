import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

// ── Analyze image (OCR + Gemini vision)
export const analyzeImage = (formData) =>
  api.post('/image-processing', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })

// ── Query and ingest news by topic
export const queryNews = (topic) =>
  api.post('/news-api', { topic })

// ── RAG knowledge synthesis
export const queryLLM = (query) =>
  api.post('/llm-knowledge', { query })

// ── Full unified pipeline
export const runUnifiedPipeline = (formData) =>
  api.post('/unified-pipeline', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })

// ── Health check
export const checkHealth = () =>
  api.get('/health')

export default api
