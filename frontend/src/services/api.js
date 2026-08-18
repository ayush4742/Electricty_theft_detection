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

// --- SMS alerting -----------------------------------------------------------
// The backend only ever returns booleans and counts here: no Twilio
// credentials and no phone numbers are sent to the browser.
export const getAlertStatus = () => api.get('/alert-status');
export const getAlertHistory = () => api.get('/alert-history');

// The test token is typed by the user at the moment they press the button and
// is never stored in this file, in state that outlives the page, or in the
// build output.
export const sendTestAlert = (token) =>
  api.post('/test-alert', {}, { headers: { 'X-Alert-Token': token } });

export default api;

