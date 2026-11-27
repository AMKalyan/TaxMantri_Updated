import client, { API_BASE } from './client.js'

/**
 * Upload a Form 16 PDF/image for OCR extraction.
 * Returns { session_id, extracted_fields, summary, warnings }
 */
export async function uploadForm16(file) {
  const formData = new FormData()
  formData.append('file', file)
  const response = await client.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000, // OCR can take longer
  })
  return response.data
}

/**
 * Confirm OCR-extracted profile with user edits.
 * body: { session_id, edited_fields }
 * Returns { profile_id, status: 'confirmed' }
 */
export async function confirmProfile(body) {
  const response = await client.put('/profile/confirm', body)
  return response.data
}

/**
 * Create a profile from manual wizard entry.
 * body: Full UserFinancialProfile JSON
 * Returns { profile_id, session_id, status, validation_errors }
 */
export async function createProfile(body) {
  const response = await client.post('/profile', body)
  return response.data
}

/**
 * Calculate tax for a stored profile.
 * body: { profile_id }
 * Returns full TaxResult JSON
 */
export async function calculateTax(profileId) {
  const response = await client.post('/calculate', { profile_id: profileId })
  return response.data
}

/**
 * Get ITR-1 field mapping for a profile.
 * Returns array of { itr1_field, schedule, value, source_field, regime, note }
 */
export async function getITR1Mapping(profileId) {
  const response = await client.get(`/itr1-mapping/${profileId}`)
  return response.data
}

/**
 * Download the tax report PDF for a profile.
 * Returns a Blob for browser download.
 */
export async function exportPDF(profileId) {
  const response = await client.get(`/export/${profileId}`, {
    responseType: 'blob',
  })
  return response.data
}

/**
 * Ask a tax question — RAG retrieval + LLM answer with IT Act citations.
 * question:   plain-English tax query
 * sessionId:  UUID for chat history tracking (persisted in localStorage)
 * profileId:  optional — personalises answer using user's financial profile
 *
 * Returns { answer, confidence, citations, cached }
 */
export async function queryChat(question, sessionId, profileId = null) {
  const body = { question, session_id: sessionId }
  if (profileId) body.profile_id = profileId
  const response = await client.post('/query', body)
  return response.data
}

/**
 * Fetch full Q&A chat history for a session from PostgreSQL.
 * Returns { session_id, messages: [{question, answer, confidence, created_at}] }
 */
export async function getChatHistory(sessionId) {
  const response = await client.get(`/chat/history`, { params: { session_id: sessionId } })
  return response.data
}


/**
 * DELETE /api/my-data — remove the stored profile, results, chat history and events.
 */
export async function deleteMyData({ profileId = null, sessionId = null }) {
  const response = await client.delete('/my-data', {
    data: { profile_id: profileId, session_id: sessionId },
  })
  return response.data
}

const STEP_LABELS = {
  search_tax_law: 'Checking the Income Tax Act…',
  calculate_tax: 'Calculating your tax…',
  what_if: 'Running a what-if scenario…',
  get_my_profile: 'Reading your saved profile…',
}

/**
 * POST /api/assistant?stream=true — tool-using assistant over Server-Sent Events.
 * onStep(label) is called as the assistant uses each tool.
 * Falls back to the single-shot /api/query if the assistant is unavailable (503).
 * Resolves to { answer, citations, grounded, confidence, steps }.
 */
export async function askAssistant(question, sessionId, profileId = null, onStep = () => {}) {
  const body = { question, session_id: sessionId }
  if (profileId) body.profile_id = profileId

  let res
  try {
    res = await fetch(`${API_BASE}/assistant?stream=true`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch {
    throw Object.assign(new Error('network'), { kind: 'network' })
  }
  if (res.status === 503) return { ...(await queryChat(question, sessionId, profileId)), grounded: true }
  if (!res.ok || !res.body) {
    let message = 'Something went wrong. Please try again.'
    try { message = (await res.json())?.error?.message || message } catch { /* not JSON */ }
    throw Object.assign(new Error(message), { kind: 'http', status: res.status })
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let sep
    while ((sep = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, sep)
      buffer = buffer.slice(sep + 2)
      const event = /^event: (.*)$/m.exec(block)?.[1]
      const dataLine = /^data: (.*)$/m.exec(block)?.[1]
      if (!event || !dataLine) continue
      const data = JSON.parse(dataLine)
      if (event === 'step') onStep(STEP_LABELS[data.tool] || 'Working…')
      if (event === 'done') return data
      if (event === 'error') throw Object.assign(new Error(data.message), { kind: 'http' })
    }
  }
  throw Object.assign(new Error('The answer stream ended unexpectedly.'), { kind: 'http' })
}
