const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000'

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  })

  const payload = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(payload.error || payload.message || 'Request failed')
  }

  return payload
}

export const api = {
  getMovies: (params = {}) => {
    const query = new URLSearchParams(params)
    const suffix = query.toString() ? `?${query.toString()}` : ''
    return request(`/movies${suffix}`)
  },
  createUser: (username) => request('/user', {
    method: 'POST',
    body: JSON.stringify({ username }),
  }),
  saveInteraction: (interaction) => request('/interact', {
    method: 'POST',
    body: JSON.stringify(interaction),
  }),
  getInteractions: (params = {}) => {
    const query = new URLSearchParams(params)
    const suffix = query.toString() ? `?${query.toString()}` : ''
    return request(`/interact${suffix}`)
  },
  getUserProfile: (params = {}) => {
    const query = new URLSearchParams(params)
    const suffix = query.toString() ? `?${query.toString()}` : ''
    return request(`/profile/user${suffix}`)
  },
  getSvdRecommendations: (params = {}) => {
    const query = new URLSearchParams(params)
    const suffix = query.toString() ? `?${query.toString()}` : ''
    return request(`/recommendations/svd${suffix}`)
  },
  getContentRecommendations: (params = {}) => {
    const query = new URLSearchParams(params)
    const suffix = query.toString() ? `?${query.toString()}` : ''
    return request(`/recommendations/content${suffix}`)
  },
  getFinalRecommendations: (params = {}) => {
    const query = new URLSearchParams(params)
    const suffix = query.toString() ? `?${query.toString()}` : ''
    return request(`/recommendations/final${suffix}`)
  },
  submitRecommendationFeedback: (payload) => request('/recommendations/feedback', {
    method: 'POST',
    body: JSON.stringify(payload),
  }),
  resetRecommendationFeedback: (payload) => request('/recommendations/feedback/reset', {
    method: 'POST',
    body: JSON.stringify(payload),
  }),
}

export { API_BASE_URL }
