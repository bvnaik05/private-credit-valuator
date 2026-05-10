import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const api = {
  getMarket: () =>
    axios.get(`${BASE}/api/market`).then(r => r.data),

  scoreLoan: (loan) =>
    axios.post(`${BASE}/api/score`, loan).then(r => r.data),

  analysePortfolio: (file) => {
    const form = new FormData()
    form.append('file', file)
    return axios.post(`${BASE}/api/portfolio`, form).then(r => r.data)
  },

  getDecision: () =>
    axios.get(`${BASE}/api/decide`).then(r => r.data),
}