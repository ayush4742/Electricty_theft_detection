import { Alert, Box, Card, CardContent, Chip, Stack, Typography } from '@mui/material';

const PredictionResultCard = ({ result }) => {
  if (!result || typeof result !== 'object') return null;

  const prediction = typeof result.prediction === 'string' ? result.prediction : 'Unknown';
  const isTheft = prediction === 'Theft';
  const confidence = typeof result.confidence === 'number' ? result.confidence : null;
  const risk = typeof result.risk === 'string' ? result.risk : 'Unknown';
  const meterId = typeof result.meter_id === 'string' && result.meter_id ? result.meter_id : 'N/A';
  const timestamp = typeof result.timestamp === 'string' && result.timestamp ? result.timestamp : 'N/A';
  const reason = typeof result.reason === 'string' && result.reason ? result.reason : 'No reason provided.';

  return (
    <Card sx={{ borderRadius: 4, border: `1px solid ${isTheft ? '#c0392b' : '#2e7d32'}` }}>
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
      </CardContent>
    </Card>
  );
};

export default PredictionResultCard;
