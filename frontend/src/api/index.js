import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000
})

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// 认证相关
export const authApi = {
  login: (data) => api.post('/auth/login', data),
  register: (data) => api.post('/auth/register', data),
  getMe: () => api.get('/auth/me')
}

// 考试相关
export const examApi = {
  getList: () => api.get('/exams/'),
  getDetail: (id) => api.get(`/exams/${id}`),
  create: (data) => api.post('/exams/', data),
  update: (id, data) => api.put(`/exams/${id}`, data),
  delete: (id) => api.delete(`/exams/${id}`)
}

// 题目相关
export const questionApi = {
  getList: (examId) => api.get(`/questions/exam/${examId}`),
  create: (data) => api.post('/questions/', data),
  update: (id, data) => api.put(`/questions/${id}`, data),
  delete: (id) => api.delete(`/questions/${id}`)
}

// 答题相关
export const submissionApi = {
  getMyList: () => api.get('/submissions/my'),
  startExam: (examId) => api.post('/submissions/start', { exam_id: examId }),
  submitAnswer: (submissionId, data) => api.post(`/submissions/${submissionId}/answer`, data),
  submitExam: (submissionId) => api.post(`/submissions/${submissionId}/submit`),
  getDetail: (id) => api.get(`/submissions/${id}`)
}

// 用户相关
export const userApi = {
  getList: () => api.get('/users/'),
  getDetail: (id) => api.get(`/users/${id}`),
  delete: (id) => api.delete(`/users/${id}`)
}

export default api
