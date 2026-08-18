import axios from 'axios';

const API_BASE_URL = 'http://localhost:5000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 600000,
});

export const getHealthStatus = () => api.get('/');
export const getModelInfo = () => api.get('/model-info');
export const getPredictionHistory = () => api.get('/history');
export const getDashboardStats = () => api.get('/dashboard');
export const predictJson = (payload) => api.post('/predict', payload);
export const predictCsv = (formData) => api.post('/predict-csv', formData);
export const explainPrediction = (payload) => api.post('/explain', payload);
export const explainFromHistory = (predictionId, topN = 10) => 
  api.get(`/history/${predictionId}/explain`, { params: { top_n: topN } });

export default api;

