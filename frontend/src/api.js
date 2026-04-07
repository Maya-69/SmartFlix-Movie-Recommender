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
  getSvdRecommendations: (params = {}) => {
    const query = new URLSearchParams(params)
    const suffix = query.toString() ? `?${query.toString()}` : ''
    return request(`/recommend/svd${suffix}`)
  },
  getSvdNnRecommendations: (params = {}) => {
    const query = new URLSearchParams(params)
    const suffix = query.toString() ? `?${query.toString()}` : ''
    return request(`/recommend/svd-nn${suffix}`)
  },
  getFullRecommendations: (params = {}) => {
    const query = new URLSearchParams(params)
    const suffix = query.toString() ? `?${query.toString()}` : ''
    return request(`/recommend/full${suffix}`)
  },
  getNnMetrics: () => request('/metrics/nn'),
  getUserProfile: (params = {}) => {
    const query = new URLSearchParams(params)
    const suffix = query.toString() ? `?${query.toString()}` : ''
    return request(`/profile/user${suffix}`)
  },
}

export { API_BASE_URL }
