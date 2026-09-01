import axios from 'axios';

const API_BASE_URL = 'http://localhost:5000';

// Exported so components can build absolute links for browser-initiated
// downloads, which do not go through axios and would otherwise resolve
// against the dev-server origin (port 3000) instead of the API (port 5000).
export const API_BASE = API_BASE_URL;

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 600000,
});

export const getHealthStatus = () => api.get('/');
export const getPredictionHistory = () => api.get('/history');
export const getDashboardStats = () => api.get('/dashboard');
export const predictJson = (payload) => api.post('/predict', payload);
export const predictCsv = (formData) => api.post('/predict-csv', formData);

// --- Authentication ---------------------------------------------------------
// Passwords are sent once, over the request body, and are hashed with PBKDF2 on
// the server before storage — nothing here ever holds a plaintext password.
// The bearer token returned by sign-in is attached to later requests by an
// interceptor registered in AuthContext, so no page has to remember the header.
export const signupRequest = (payload) => api.post('/auth/signup', payload);
export const loginRequest = (payload) => api.post('/auth/login', payload);
export const logoutRequest = () => api.post('/auth/logout');
export const getAuthStatus = () => api.get('/auth/status');

// Takes the token explicitly so the boot-time session check does not depend on
// the interceptor having been registered first.
export const getMe = (token) =>
  api.get('/auth/me', token ? { headers: { Authorization: `Bearer ${token}` } } : {});

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

// --- Meter lookup -----------------------------------------------------------
// Everything returned here is derived from rows the user's own CSV uploads
// created. A meter that was never uploaded returns 404 rather than a made-up
// profile.
export const searchMeters = (q = '', limit = 25) =>
  api.get('/meters/search', { params: { q, limit } });
export const getMeterProfile = (meterId, full = false) =>
  api.get(`/meters/${encodeURIComponent(meterId)}`, { params: full ? { full: 1 } : {} });

// --- CSV upload persistence -------------------------------------------------
// The backend records one row per upload run (filename, counts, and the id range
// of the predictions it produced). The Upload page reads the latest run when it
// mounts, which is what restores its state after navigation. These are reads -
// they never re-run a prediction or create a record.
export const getLatestUpload = () => api.get('/uploads/latest');
export const getUploads = (limit = 10) => api.get('/uploads', { params: { limit } });
export const getUpload = (batchId) => api.get(`/uploads/${batchId}`);
export const clearUploads = () => api.delete('/uploads');

// --- Network dataset --------------------------------------------------------
// Lets the distribution network come from an uploaded CSV instead of the
// seeder script. `getTransformerDataset` reports the current source honestly
// (upload / seed / none) so the page can say whether its figures are simulated.
export const getTransformerDataset = () => api.get('/transformers/dataset');
export const uploadTransformerDataset = (file) => {
  const form = new FormData();
  form.append('file', file);
  return api.post('/transformers/upload', form);
};
export const clearTransformerDataset = () => api.delete('/transformers/dataset');

export default api;
