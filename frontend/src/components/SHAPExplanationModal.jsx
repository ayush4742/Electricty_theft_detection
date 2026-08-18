import {
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,
  DialogContent,
  DialogTitle,
  LinearProgress,
  Stack,
  Typography,
} from '@mui/material';

const SHAPExplanationModal = ({ open, onClose, explanation, isLoading, error }) => {
  if (!open) return null;

  if (isLoading) {
    return (
      <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
        <DialogTitle>Generating Explanation...</DialogTitle>
        <DialogContent sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '200px' }}>
          <CircularProgress />
        </DialogContent>
      </Dialog>
    );
  }

  if (error) {
    return (
      <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
        <DialogTitle>Explanation Error</DialogTitle>
        <DialogContent>
          <Typography color="error">{error}</Typography>
        </DialogContent>
      </Dialog>
    );
  }

  if (!explanation) {
    return (
      <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
        <DialogTitle>Explanation</DialogTitle>
        <DialogContent>
          <Typography color="text.secondary">No explanation available.</Typography>
        </DialogContent>
      </Dialog>
    );
  }

  const prediction = explanation.prediction || 'Unknown';
  const risk = explanation.risk || 'Unknown';
  const confidence = explanation.confidence || 'N/A';
  const explainableFeatures = explanation.explanation || [];

  const isTheft = prediction === 'Theft';

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle sx={{ background: isTheft ? '#f44336' : '#2e7d32', color: 'white', fontWeight: 700 }}>
        Why this prediction?
      </DialogTitle>
      <DialogContent sx={{ mt: 2 }}>
        <Stack spacing={3}>
          {/* Summary */}
          <Card sx={{ background: isTheft ? '#ffebee' : '#e8f5e9' }}>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={2}>
                <Stack>
                  <Typography variant="body2" color="text.secondary">
                    Prediction
                  </Typography>
                  <Typography variant="h6" fontWeight={700}>
                    {prediction}
                  </Typography>
                </Stack>
                <Stack>
                  <Typography variant="body2" color="text.secondary">
                    Risk Level
                  </Typography>
                  <Chip label={risk} color={isTheft ? 'error' : 'success'} />
                </Stack>
                <Stack>
                  <Typography variant="body2" color="text.secondary">
                    Confidence
                  </Typography>
                  <Typography variant="h6" fontWeight={700}>
                    {confidence}%
                  </Typography>
                </Stack>
              </Stack>
            </CardContent>
          </Card>

          {/* Explanation */}
          <Box>
            <Typography variant="h6" fontWeight={700} mb={2}>
              Top Contributing Factors:
            </Typography>

            <Stack spacing={2}>
              {explainableFeatures.length > 0 ? (
                explainableFeatures.map((feature, index) => {
                  const isPositive = feature.impact === 'positive';
                  const shap_value = parseFloat(feature.shap_value) || 0;
                  const abs_value = Math.abs(shap_value);
                  const max_value = Math.max(...explainableFeatures.map((f) => Math.abs(f.shap_value)), 1);

                  return (
                    <Card key={index} variant="outlined">
                      <CardContent sx={{ py: 1.5, px: 2 }}>
                        <Stack spacing={0.5}>
                          <Stack direction="row" justifyContent="space-between" alignItems="center">
                            <Stack direction="row" spacing={1} alignItems="center" flex={1}>
                              <Typography variant="body2" sx={{ fontWeight: 600, minWidth: '30px' }}>
                                #{index + 1}
                              </Typography>
                              <Typography variant="body2" fontWeight={700} sx={{ fontSize: '0.95rem' }}>
                                {feature.feature}
                              </Typography>
                            </Stack>
                            <Chip
                              label={`${isPositive ? '+' : ''}${shap_value.toFixed(4)}`}
                              size="small"
                              variant="filled"
                              color={isPositive ? 'error' : 'success'}
                              sx={{ color: 'white', ml: 1 }}
                            />
                          </Stack>

                          {/* Visual bar */}
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <LinearProgress
                              variant="determinate"
                              value={(abs_value / max_value) * 100}
                              sx={{
                                flex: 1,
                                height: 5,
                                borderRadius: 3,
                                backgroundColor: '#e0e0e0',
                                '& .MuiLinearProgress-bar': {
                                  backgroundColor: isPositive ? '#f44336' : '#2e7d32',
                                  borderRadius: 3,
                                },
                              }}
                            />
                          </Box>

                          {/* Direction description */}
                          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                            {isPositive ? '↑ Increased' : '↓ Decreased'} {isTheft ? 'theft' : 'normal'} probability
                          </Typography>
                        </Stack>
                      </CardContent>
                    </Card>
                  );
                })
              ) : (
                <Typography color="text.secondary">No explanation features available.</Typography>
              )}
            </Stack>
          </Box>

          {/* Legend */}
          <Box sx={{ pt: 1, borderTop: '1px solid #e0e0e0' }}>
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.8rem' }}>
              <strong style={{ color: '#f44336' }}>+Positive</strong> features pushed prediction toward {isTheft ? 'THEFT' : 'NORMAL'} •{' '}
              <strong style={{ color: '#2e7d32' }}>-Negative</strong> features pulled away
            </Typography>
          </Box>
        </Stack>
      </DialogContent>
    </Dialog>
  );
};

export default SHAPExplanationModal;
