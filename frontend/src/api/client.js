import axios from 'axios'
import toast from 'react-hot-toast'

// In production the frontend (Vercel) calls the backend (Render) directly.
// VITE_API_URL is the backend origin, e.g. https://taxmantri-api.onrender.com
// In local dev it is unset and Vite proxies /api to localhost:8000.
export const API_BASE = `${(import.meta.env.VITE_API_URL || '').replace(/\/$/, '')}/api`

const client = axios.create({
  baseURL: API_BASE,
  timeout: 90000, // free-tier backend may need ~60s to wake up
  headers: {
    'Content-Type': 'application/json',
  },
})

// Response interceptor — normalise error shape
client.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const data = error.response?.data

    // Backend returns { error: { code, message, details } }
    if (data?.error?.message) {
      toast.error(data.error.message)
    } else if (status === 404) {
      toast.error('Resource not found.')
    } else if (status === 422) {
      toast.error('Validation error. Please check your inputs.')
    } else if (status >= 500) {
      toast.error('Server error. Please try again.')
    } else if (status === 429) {
      toast.error('Too many requests — please wait a minute and try again.')
    } else if (!error.response) {
      toast.error('Cannot reach the server. It may be waking up — please try again in a moment.')
    }

    return Promise.reject(error)
  },
)

export default client
