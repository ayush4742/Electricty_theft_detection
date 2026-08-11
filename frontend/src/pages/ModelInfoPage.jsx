import { Alert, Box, CircularProgress, Container, Stack, Typography } from '@mui/material';
import { useEffect, useState } from 'react';
import ModelInfoCard from '../components/ModelInfoCard';
import { getModelInfo } from '../services/api';

const ModelInfoPage = () => {
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadModelInfo = async () => {
      try {
        const response = await getModelInfo();
        setInfo(response.data);
      } catch (err) {
        setError('Unable to fetch model information.');
      } finally {
        setLoading(false);
      }
    };

    loadModelInfo();
  }, []);

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      <Stack spacing={3}>
        <Box>
          <Typography variant="h4" fontWeight={700}>
            Model Information
          </Typography>
          <Typography color="text.secondary" sx={{ mt: 1 }}>
            Review the loaded machine learning model configuration.
          </Typography>
        </Box>

        {loading ? (
          <Box display="flex" justifyContent="center" py={6}>
            <CircularProgress />
          </Box>
        ) : error ? (
          <Alert severity="error">{error}</Alert>
        ) : (
          <ModelInfoCard info={info} />
        )}
      </Stack>
    </Container>
  );
};

export default ModelInfoPage;
