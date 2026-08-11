import { Alert, Box, CircularProgress, Container, Grid, Stack, Typography } from '@mui/material';
import { motion } from 'framer-motion';
import { useEffect, useState } from 'react';
import DashboardCards from '../components/DashboardCards';
import { TheftDonutCard, PredictionsBarCard, ConfidenceLineCard, LatestPredictionCard, LiveGridLoadCard, LiveDetectionGaugeCard } from '../components/Charts';
import { getDashboardStats } from '../services/api';
import { useLiveDashboard } from '../hooks/useLiveDashboard';

const DashboardPage = () => {
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadDashboard = async () => {
      try {
        const response = await getDashboardStats();
        setDashboardData(response.data);
        setError('');
      } catch (err) {
        setError('Unable to load dashboard data.');
        setDashboardData(null);
      } finally {
        setLoading(false);
      }
    };

    loadDashboard();
  }, []);

  const live = useLiveDashboard(dashboardData, { intervalMs: 3000, windowSize: 12 });
  const stats = live.stats;
  const hasPredictions = stats.totalPredictions > 0;

  return (
    <Container maxWidth="xl" sx={{ py: 2 }}>
      <Stack spacing={3}>
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
          <Box
            sx={{
              p: { xs: 2.5, md: 3 },
              borderRadius: '16px',
              position: 'relative',
              overflow: 'hidden',
              background: 'linear-gradient(135deg, #171f38 0%, #121a2e 100%)',
              border: '1px solid rgba(255,255,255,0.08)',
              boxShadow: '0 20px 50px rgba(0,0,0,0.35)',
              '&::before': {
                content: '""',
                position: 'absolute',
                inset: 0,
                background: 'radial-gradient(circle at 85% 0%, rgba(139,92,246,0.22), transparent 55%)',
                pointerEvents: 'none',
              },
            }}
          >
            <Typography
              variant="h4"
              fontWeight={800}
              sx={{
                position: 'relative',
                background: 'linear-gradient(90deg, #a78bfa, #22d3ee)',
                backgroundClip: 'text',
                WebkitBackgroundClip: 'text',
                color: 'transparent',
              }}
            >
              Dashboard
            </Typography>
            <Typography sx={{ mt: 1, position: 'relative', color: '#c3c9dc' }}>
              Monitor live predictions and inspect abnormal usage patterns with a modern AI analytics view.
            </Typography>
          </Box>
        </motion.div>

        {loading ? (
          <Box display="flex" justifyContent="center" py={6}>
            <CircularProgress sx={{ color: '#8b5cf6' }} />
          </Box>
        ) : error ? (
          <Alert severity="error">{error}</Alert>
        ) : (
          <>
            <DashboardCards stats={stats} />
            <Grid container spacing={3}>
              <Grid item xs={12} sm={6} md={4} sx={{ display: 'flex' }}>
                <div style={{ width: '100%' }}>
                  <ConfidenceLineCard history={live.history} />
                </div>
              </Grid>
              <Grid item xs={12} sm={6} md={4} sx={{ display: 'flex' }}>
                <div style={{ width: '100%' }}>
                  <LiveGridLoadCard />
                </div>
              </Grid>
              <Grid item xs={12} sm={6} md={4} sx={{ display: 'flex' }}>
                <div style={{ width: '100%' }}>
                  <LiveDetectionGaugeCard />
                </div>
              </Grid>

              <Grid item xs={12} sm={6} md={4} sx={{ display: 'flex' }}>
                <div style={{ width: '100%' }}>
                  <TheftDonutCard history={live.history} />
                </div>
              </Grid>
              <Grid item xs={12} sm={6} md={4} sx={{ display: 'flex' }}>
                <motion.div
                  initial={{ opacity: 0, x: 16 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3 }}
                  style={{ width: '100%' }}
                >
                  <LatestPredictionCard latestPrediction={live.latestPrediction} hasPredictions={hasPredictions} />
                </motion.div>
              </Grid>
              <Grid item xs={12} sm={6} md={4} sx={{ display: 'flex' }}>
                <div style={{ width: '100%' }}>
                  <PredictionsBarCard history={live.history} />
                </div>
              </Grid>
            </Grid>
          </>
        )}
      </Stack>
    </Container>
  );
};

export default DashboardPage;