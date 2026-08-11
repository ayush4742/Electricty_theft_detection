import { Box, Card, CardContent, Grid, Stack, Typography } from '@mui/material';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import ReportProblemIcon from '@mui/icons-material/ReportProblem';
import VerifiedUserIcon from '@mui/icons-material/VerifiedUser';
import ShieldIcon from '@mui/icons-material/Shield';
import SpeedIcon from '@mui/icons-material/Speed';
import { motion } from 'framer-motion';

const cards = [
  { key: 'total', title: 'Total Processed', color: '#22d3ee', icon: <TrendingUpIcon fontSize="medium" /> },
  { key: 'theft', title: 'Theft Detected', color: '#f16465', icon: <ReportProblemIcon fontSize="medium" /> },
  { key: 'normal', title: 'Normal', color: '#34d399', icon: <VerifiedUserIcon fontSize="medium" /> },
  { key: 'confidence', title: 'Avg Confidence', color: '#8b5cf6', icon: <ShieldIcon fontSize="medium" /> },
  { key: 'speed', title: 'Processing Time', color: '#f5a623', icon: <SpeedIcon fontSize="medium" /> },
];

const DashboardCards = ({ stats }) => {
  const hasData = stats.totalPredictions > 0;

  const values = {
    total: hasData ? stats.totalPredictions.toLocaleString() : '—',
    theft: hasData ? stats.theftPredictions.toLocaleString() : '—',
    normal: hasData ? stats.normalPredictions.toLocaleString() : '—',
    confidence: hasData ? `${(stats.averageConfidence ?? 0).toFixed(1)}%` : '—',
    speed: hasData ? `${stats.processingTime ?? 0}s` : '—',
  };

  return (
    <Grid container spacing={2.5} sx={{ mb: 3 }}>
      {cards.map((card, index) => (
        <Grid item xs={12} sm={6} md={2.4} key={card.key}>
          <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25, delay: index * 0.05 }}>
            <Card
              sx={{
                borderRadius: '16px',
                position: 'relative',
                overflow: 'hidden',
                border: '1px solid rgba(255,255,255,0.08)',
                '&::before': {
                  content: '""',
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  right: 0,
                  height: 3,
                  background: card.color,
                },
              }}
            >
              <CardContent>
                <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={2}>
                  <Box>
                    <Typography
                      variant="overline"
                      sx={{ color: 'text.secondary', fontWeight: 600, letterSpacing: '0.06em', lineHeight: 1.4 }}
                    >
                      {card.title}
                    </Typography>
                    <motion.div key={values[card.key]} initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
                      <Typography
                        variant="h5"
                        sx={{ mt: 0.5, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700 }}
                      >
                        {values[card.key]}
                      </Typography>
                    </motion.div>
                  </Box>
                  <Box
                    sx={{
                      color: card.color,
                      backgroundColor: `${card.color}22`,
                      borderRadius: '50%',
                      width: 44,
                      height: 44,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}
                  >
                    {card.icon}
                  </Box>
                </Stack>
              </CardContent>
            </Card>
          </motion.div>
        </Grid>
      ))}
    </Grid>
  );
};

export default DashboardCards;