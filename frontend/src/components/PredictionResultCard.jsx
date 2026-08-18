import { Alert, Box, Button, Card, CardContent, Chip, Stack, Typography } from '@mui/material';
import { useState } from 'react';

import PredictionExplanation from './PredictionExplanation';
import { explainPrediction } from '../services/api';

const PredictionResultCard = ({ result, readings, featureNames }) => {
  const [explanationOpen, setExplanationOpen] = useState(false);
  const [explanation, setExplanation] = useState(null);
  const [isLoadingExplanation, setIsLoadingExplanation] = useState(false);
  const [explanationError, setExplanationError] = useState(null);

  if (!result || typeof result !== 'object') return null;

  const prediction = typeof result.prediction === 'string' ? result.prediction : 'Unknown';
  const isTheft = prediction === 'Theft';
  const confidence = typeof result.confidence === 'number' ? result.confidence : null;
  const risk = typeof result.risk === 'string' ? result.risk : 'Unknown';
  const meterId = typeof result.meter_id === 'string' && result.meter_id ? result.meter_id : 'N/A';
  const timestamp = typeof result.timestamp === 'string' && result.timestamp ? result.timestamp : 'N/A';
  const reason = typeof result.reason === 'string' && result.reason ? result.reason : 'No reason provided.';

  const handleExplainClick = async () => {
    if (!readings) {
      setExplanationError('Readings data not available for explanation.');
      return;
    }

    setExplanationOpen(true);
    setIsLoadingExplanation(true);
    setExplanationError(null);

    try {
      const payload = { readings };
      if (featureNames && Array.isArray(featureNames)) {
        payload.feature_names = featureNames;
      }
      const response = await explainPrediction(payload);
      setExplanation(response.data);
    } catch (error) {
      console.error('Failed to generate explanation:', error);
      setExplanationError(error.response?.data?.message || 'Failed to generate explanation. Please try again.');
    } finally {
      setIsLoadingExplanation(false);
    }
  };

  const handleCloseExplanation = () => {
    setExplanationOpen(false);
  };

  return (
    <>
      <Card sx={{ borderRadius: 4, border: `1px solid ${isTheft ? '#f44336' : '#2e7d32'}` }}>
        <CardContent>
          <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" alignItems="flex-start" spacing={2}>
            <Box>
              <Typography variant="h6" fontWeight={700}>
                Prediction Result
              </Typography>
              <Typography color="text.secondary" sx={{ mt: 1 }}>
                {reason}
              </Typography>
            </Box>
            <Chip label={prediction} color={isTheft ? 'error' : 'success'} sx={{ fontWeight: 700 }} />
          </Stack>
          <Stack spacing={1} sx={{ mt: 2 }}>
            <Alert severity={isTheft ? 'error' : 'success'}>
              Risk: {risk} | Confidence: {confidence !== null ? `${confidence}%` : 'N/A'}
            </Alert>
            <Typography variant="body2" color="text.secondary">
              Meter ID: {meterId}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Timestamp: {timestamp}
            </Typography>
          </Stack>
          {readings && (
            <Box sx={{ mt: 2 }}>
              <Button
                variant="outlined"
                size="small"
                onClick={handleExplainClick}
                sx={{
                  borderColor: isTheft ? '#f44336' : '#2e7d32',
                  color: isTheft ? '#f44336' : '#2e7d32',
                  '&:hover': {
                    backgroundColor: isTheft ? '#ffebee' : '#e8f5e9',
                  },
                }}
              >
                Why this prediction?
              </Button>
              {explanationError && (
                <Typography variant="caption" color="error" sx={{ display: 'block', mt: 1 }}>
                  {explanationError}
                </Typography>
              )}
            </Box>
          )}
        </CardContent>
      </Card>

      <PredictionExplanation open={explanationOpen} onClose={handleCloseExplanation} explanation={explanation} isLoading={isLoadingExplanation} />
    </>
  );
};

export default PredictionResultCard;

