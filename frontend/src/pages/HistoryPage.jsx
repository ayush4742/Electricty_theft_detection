import { Alert, Box, CircularProgress, Container, Stack, Typography } from '@mui/material';
import { useEffect, useState } from 'react';
import ErrorBoundary from '../components/ErrorBoundary';
import HistoryTable from '../components/HistoryTable';
import { getPredictionHistory } from '../services/api';

const normalizeHistoryResponse = (payload) => {
  if (Array.isArray(payload)) {
    return payload;
  }

  if (payload && typeof payload === 'object') {
    if (Array.isArray(payload.history)) {
      return payload.history;
    }
    if (Array.isArray(payload.data)) {
      return payload.data;
    }
    if (Array.isArray(payload.results)) {
      return payload.results;
    }
  }

  return [];
};

const HistoryPage = () => {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadHistory = async () => {
      try {
        const response = await getPredictionHistory();
        console.log('History API response:', response?.data ?? response);
        const normalizedHistory = normalizeHistoryResponse(response?.data ?? response);
        setHistory(normalizedHistory.filter((item) => item && typeof item === 'object'));
      } catch (err) {
        console.error('History API error:', err);
        setError(err?.response?.data?.message || err?.message || 'Unable to fetch prediction history.');
      } finally {
        setLoading(false);
      }
    };

    loadHistory();
  }, []);

  return (
    <ErrorBoundary>
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Stack spacing={3}>
          <Box>
            <Typography variant="h4" fontWeight={700}>
              Prediction History
            </Typography>
            <Typography color="text.secondary" sx={{ mt: 1 }}>
              Review all saved predictions and inspect their confidence and risk levels.
            </Typography>
          </Box>

          {loading ? (
            <Box display="flex" justifyContent="center" py={6}>
              <CircularProgress />
            </Box>
          ) : error ? (
            <Alert severity="error">{error}</Alert>
          ) : history.length === 0 ? (
            <Alert severity="info">No prediction history available.</Alert>
          ) : (
            <HistoryTable history={history} />
          )}
        </Stack>
      </Container>
    </ErrorBoundary>
  );
};

export default HistoryPage;
