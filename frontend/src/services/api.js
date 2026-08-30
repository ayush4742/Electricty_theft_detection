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

// --- Distribution-transformer energy balance --------------------------------
// Compares energy supplied by each transformer against energy billed to the
// meters under it. A persistent gap is unbilled energy, i.e. theft.
export const getNetworkKpis = (days = 30) => api.get('/network-kpis', { params: { days } });
export const getTransformers = (days = 30) => api.get('/transformers', { params: { days } });
export const getHighLossTransformers = (days = 30) =>
  api.get('/transformers/high-loss', { params: { days } });
export const getTransformerDetail = (id, days = 30) =>
  api.get(`/transformers/${id}`, { params: { days } });
export const getTransformerTrend = (id, days = 30) =>
  api.get(`/transformers/${id}/trend`, { params: { days } });

// --- AI assistant -----------------------------------------------------------
// The agent answers by calling tools that query the backend database. The
// response includes which tools ran, so the UI can show where a number came
// from instead of asking the user to trust it.
export const getAgentStatus = () => api.get('/agent/status');
export const getAgentSuggestions = () => api.get('/agent/suggestions');
export const askAgent = (question, history = []) =>
  api.post('/agent/ask', { question, history });

export default api;
