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
import { useState } from 'react';

const PredictionExplanation = ({ open, onClose, explanation, isLoading }) => {
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

  if (!explanation) {
    return (
      <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
        <DialogTitle>Explanation</DialogTitle>
        <DialogContent>
          <Typography color="error">Unable to generate explanation. Please try again.</Typography>
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
        Why was this prediction made?
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
              Top Contributing Consumption Features:
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
                      <CardContent>
                        <Stack spacing={1}>
                          <Stack direction="row" justifyContent="space-between" alignItems="center">
                            <Stack direction="row" spacing={1} alignItems="center" flex={1}>
                              <Typography variant="body2" sx={{ fontWeight: 600, minWidth: '40px' }}>
                                #{index + 1}
                              </Typography>
                              <Typography variant="body2" fontWeight={700}>
                                {feature.feature}
                              </Typography>
                            </Stack>
                            <Chip
                              label={`SHAP: ${isPositive ? '+' : ''}${shap_value.toFixed(4)}`}
                              size="small"
                              variant="filled"
                              color={isPositive ? 'error' : 'success'}
                              sx={{ color: 'white' }}
                            />
                          </Stack>

                          {/* Direction description */}
                          <Typography variant="caption" color="text.secondary">
                            {isPositive ? '↑' : '↓'} {feature.direction.replace(/_/g, ' ')}
                          </Typography>

                          {/* Visual bar */}
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
                            <LinearProgress
                              variant="determinate"
                              value={(abs_value / max_value) * 100}
                              sx={{
                                flex: 1,
                                height: 6,
                                borderRadius: 3,
                                backgroundColor: '#e0e0e0',
                                '& .MuiLinearProgress-bar': {
                                  backgroundColor: isPositive ? '#f44336' : '#2e7d32',
                                  borderRadius: 3,
                                },
                              }}
                            />
                            <Typography variant="caption" sx={{ minWidth: '40px', textAlign: 'right' }}>
                              {abs_value.toFixed(3)}
                            </Typography>
                          </Box>
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
          <Box sx={{ pt: 2, borderTop: '1px solid #e0e0e0' }}>
            <Typography variant="caption" color="text.secondary">
              <strong>Positive SHAP:</strong> Feature pushed the prediction toward <strong>{isTheft ? 'Theft' : 'Normal'}</strong>.
            </Typography>
            <br />
            <Typography variant="caption" color="text.secondary">
              <strong>Negative SHAP:</strong> Feature pushed the prediction away from <strong>{isTheft ? 'Theft' : 'Normal'}</strong>.
            </Typography>
          </Box>
        </Stack>
      </DialogContent>
    </Dialog>
  );
};

export default PredictionExplanation;
