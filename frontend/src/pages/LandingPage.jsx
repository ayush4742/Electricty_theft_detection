import { Box, Button, Card, CardContent, Chip, Divider, Grid, Stack, Typography } from '@mui/material';
import ArrowForwardIcon from '@mui/icons-material/ArrowForwardRounded';
import BoltIcon from '@mui/icons-material/BoltRounded';
import InsightsIcon from '@mui/icons-material/InsightsRounded';
import HubIcon from '@mui/icons-material/HubRounded';
import ManageSearchIcon from '@mui/icons-material/ManageSearchRounded';
import ElectricMeterIcon from '@mui/icons-material/ElectricMeterRounded';
import FactCheckIcon from '@mui/icons-material/FactCheckRounded';
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActiveRounded';
import SmartToyIcon from '@mui/icons-material/SmartToyRounded';
import { Link as RouterLink } from 'react-router-dom';
import SmartMeterArt from '../components/SmartMeterArt';
import { ink, line, radius, status, statusFill, surface } from '../theme/tokens';

const CAPABILITIES = [
  { icon: <BoltIcon />, title: 'AI Theft Detection',
    body: 'A trained classifier scores each meter’s consumption history and returns a verdict with a confidence and a risk band.' },
  { icon: <InsightsIcon />, title: 'Explainable Predictions',
    body: 'SHAP attributions show which readings drove a decision. Accusing a consumer is a legal act, so a score alone is not enough.' },
  { icon: <HubIcon />, title: 'Federated Learning',
    body: 'FedAvg and FedProx across simulated clients, so a shared model can be trained without pooling raw consumption data.' },
  { icon: <ManageSearchIcon />, title: 'Meter Lookup',
    body: 'Search any meter and see its full record: verdict history, consumption trace, zero-usage runs and sustained drops.' },
  { icon: <ElectricMeterIcon />, title: 'Network Health',
    body: 'Energy supplied by each distribution transformer against energy billed under it. A persistent gap is unbilled energy.' },
  { icon: <FactCheckIcon />, title: 'Investigation Priority',
    body: 'Model confidence blended with transformer loss, producing a ranked shortlist instead of an undifferentiated pile of alerts.' },
  { icon: <NotificationsActiveIcon />, title: 'Automated Alerts',
    body: 'Telegram or SMS on a theft prediction, with per-meter cooldown, batch caps and a confidence floor to prevent spam.' },
  { icon: <SmartToyIcon />, title: 'AI Assistant',
    body: 'Ask questions in plain language. The assistant answers by querying the database and never states a figure it did not retrieve.' },
];

const WORKFLOW = [
  { step: 'Smart meter data', body: 'Daily consumption readings are uploaded as CSV.' },
  { step: 'AI detection', body: 'Each meter is scored by the trained model.' },
  { step: 'Risk & anomaly analysis', body: 'Confidence, risk band and SHAP explanation per prediction.' },
  { step: 'Energy balance verification', body: 'Supplied versus billed energy checked at transformer level.' },
  { step: 'Investigation priority', body: 'Both signals combined into one ranked shortlist.' },
  { step: 'Alerts & monitoring', body: 'Field teams notified; outcomes tracked on the dashboard.' },
];

const USE_CASE = [
  'Identify meters whose consumption pattern breaks.',
  'Cross-check them against network-level energy imbalance.',
  'Prioritise the cases worth an inspector’s day.',
  'Investigate on site.',
  'Record the outcome — confirmed, false alarm, or meter fault.',
  'Alert the team automatically when new cases appear.',
  'Feed inspection results back so future models improve.',
];

const Section = ({ eyebrow, title, children, sx }) => (
  <Box component="section" sx={{ mt: { xs: 6, md: 9 }, ...sx }}>
    {eyebrow && (
      <Typography variant="overline" sx={{ color: ink.muted, display: 'block', mb: 0.5 }}>
        {eyebrow}
      </Typography>
    )}
    <Typography variant="h4" sx={{ mb: 2 }}>{title}</Typography>
    {children}
  </Box>
);

const LandingPage = () => (
  <Box>
    {/* ---------------------------------------------------------------- hero */}
    <Card sx={{ borderRadius: `${radius.xl}px`, overflow: 'hidden' }}>
      <CardContent sx={{ p: { xs: 3, md: 5 } }}>
        <Grid container spacing={{ xs: 3, md: 5 }} alignItems="center">
          <Grid item xs={12} md={6.5}>
            <Chip
              size="small"
              label="Electricity utility platform"
              sx={{ mb: 2, backgroundColor: surface.sunken, color: ink.secondary, fontWeight: 600 }}
            />
            <Typography
              variant="h2"
              sx={{ fontSize: { xs: '2.2rem', md: '3.1rem' }, lineHeight: 1.05, mb: 1.5 }}
            >
              EnergyGuard
            </Typography>
            <Typography variant="h6" sx={{ color: ink.primary, fontWeight: 600, mb: 1.5 }}>
              AI-Based Electricity Theft Detection &amp; Monitoring System
            </Typography>
            <Typography variant="body1" sx={{ color: ink.secondary, maxWidth: 560, mb: 3.5 }}>
              Detect suspicious electricity consumption, investigate high-risk meters, and monitor
              distribution-network losses using machine learning and privacy-preserving Federated
              Learning.
            </Typography>

            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
              <Button
                component={RouterLink}
                to="/signup"
                variant="contained"
                size="large"
                endIcon={<ArrowForwardIcon />}
              >
                Get started
              </Button>
              <Button component={RouterLink} to="/login" variant="outlined" size="large">
                Sign in
              </Button>
            </Stack>
          </Grid>

          <Grid item xs={12} md={5.5}>
            <SmartMeterArt />
          </Grid>
        </Grid>
      </CardContent>
    </Card>

    {/* --------------------------------------------------------------- about */}
    <Section eyebrow="About" title="What EnergyGuard is">
      <Grid container spacing={3}>
        <Grid item xs={12} md={7}>
          <Typography variant="body1" sx={{ color: ink.secondary, mb: 2 }}>
            EnergyGuard is an AI-based electricity theft detection and monitoring platform designed
            to help electricity utilities identify suspicious consumption patterns, prioritise
            investigations, and monitor distribution-network losses.
          </Typography>
          <Typography variant="body1" sx={{ color: ink.secondary }}>
            The platform combines machine learning, explainable AI, transformer-level energy-balance
            analysis and Federated Learning to support privacy-aware electricity theft detection. It
            produces a ranked shortlist for inspection — it does not, and cannot, confirm theft on
            its own. Only a field visit does that.
          </Typography>
        </Grid>
        <Grid item xs={12} md={5}>
          <Card sx={{ backgroundColor: surface.sunken, height: '100%' }}>
            <CardContent>
              <Typography variant="overline" sx={{ color: ink.muted }}>Why two signals</Typography>
              <Typography variant="body2" sx={{ color: ink.secondary, mt: 1 }}>
                A model alone can only say a pattern looks odd. An energy balance can only say
                energy went missing from a cluster, not which household took it. Used together, a
                flagged meter under a transformer that is provably losing energy is a far stronger
                case than either signal on its own — and a model hit under a healthy transformer is
                usually a false positive worth deprioritising.
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Section>

    {/* -------------------------------------------------------- how it works */}
    <Section eyebrow="Pipeline" title="How it works">
      <Grid container spacing={2}>
        {WORKFLOW.map((item, index) => (
          <Grid item xs={12} sm={6} md={4} key={item.step}>
            <Card sx={{ height: '100%' }}>
              <CardContent>
                <Stack direction="row" spacing={1.5} alignItems="flex-start">
                  <Box
                    aria-hidden="true"
                    sx={{
                      minWidth: 28, height: 28, borderRadius: '50%',
                      backgroundColor: ink.primary, color: ink.onDark,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 13, fontWeight: 700,
                    }}
                  >
                    {index + 1}
                  </Box>
                  <Box>
                    <Typography variant="subtitle2">{item.step}</Typography>
                    <Typography variant="body2" sx={{ color: ink.secondary, mt: 0.5 }}>
                      {item.body}
                    </Typography>
                  </Box>
                </Stack>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Section>

    {/* -------------------------------------------------------- capabilities */}
    <Section eyebrow="Capabilities" title="What the platform does today">
      <Grid container spacing={2}>
        {CAPABILITIES.map((cap) => (
          <Grid item xs={12} sm={6} md={3} key={cap.title}>
            <Card sx={{ height: '100%' }}>
              <CardContent>
                <Box sx={{ color: ink.primary, mb: 1.25 }}>{cap.icon}</Box>
                <Typography variant="subtitle2" sx={{ mb: 0.75 }}>{cap.title}</Typography>
                <Typography variant="body2" sx={{ color: ink.secondary, fontSize: 13.5 }}>
                  {cap.body}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Section>

    {/* --------------------------------------------------- federated learning */}
    <Section eyebrow="Privacy" title="Privacy-aware Federated Learning">
      <Card>
        <CardContent sx={{ p: { xs: 2.5, md: 4 } }}>
          <Typography variant="body1" sx={{ color: ink.secondary, maxWidth: 720, mb: 3 }}>
            EnergyGuard can train a shared model across distributed clients without requiring raw
            local consumption data to be centralised. Each client trains on its own data and returns
            only model weights; the server averages those weights into a global model.
          </Typography>

          <Stack
            direction={{ xs: 'column', md: 'row' }}
            spacing={0}
            divider={
              <Box
                aria-hidden="true"
                sx={{
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: ink.muted, px: 1.5, py: { xs: 0.5, md: 0 },
                  transform: { xs: 'rotate(90deg)', md: 'none' },
                }}
              >
                →
              </Box>
            }
            sx={{ mb: 3 }}
          >
            {['Local data', 'Local training', 'Model updates', 'Global aggregation'].map((s) => (
              <Box
                key={s}
                sx={{
                  flex: 1, px: 2, py: 1.75, textAlign: 'center',
                  border: `1px solid ${line.base}`, borderRadius: `${radius.md}px`,
                  backgroundColor: surface.sunken,
                }}
              >
                <Typography variant="body2" sx={{ fontWeight: 600 }}>{s}</Typography>
              </Box>
            ))}
          </Stack>

          <Divider sx={{ mb: 2.5 }} />

          <Stack direction="row" spacing={1.5} alignItems="flex-start">
            <Chip
              size="small"
              label="Scope"
              sx={{ color: status.warning, backgroundColor: statusFill.warning, fontWeight: 700 }}
            />
            <Typography variant="body2" sx={{ color: ink.secondary }}>
              The federated clients in this project are <strong>simulated</strong> — partitions of
              one dataset standing in for substation gateways, not physical smart meters. The
              information flow is faithful: a client only ever sends weights, never readings. But
              secure aggregation, encrypted transport and differential privacy are{' '}
              <strong>not implemented</strong>. Those are the difference between this experiment and
              a system a utility could deploy.
            </Typography>
          </Stack>
        </CardContent>
      </Card>
    </Section>

    {/* ------------------------------------------------------------ use case */}
    <Section eyebrow="In practice" title="How a utility would use it">
      <Card>
        <CardContent sx={{ p: { xs: 2.5, md: 3.5 } }}>
          <Stack spacing={0} divider={<Divider sx={{ my: 1.5 }} />}>
            {USE_CASE.map((text, index) => (
              <Stack key={text} direction="row" spacing={2} alignItems="baseline">
                <Typography
                  variant="body2"
                  sx={{ color: ink.muted, fontWeight: 700, minWidth: 22, fontVariantNumeric: 'tabular-nums' }}
                >
                  {String(index + 1).padStart(2, '0')}
                </Typography>
                <Typography variant="body1" sx={{ color: ink.secondary }}>{text}</Typography>
              </Stack>
            ))}
          </Stack>
          <Typography variant="caption" sx={{ color: ink.muted, display: 'block', mt: 2.5 }}>
            This describes how the platform is designed to be used. It is a final-year research
            project and has not been deployed with an electricity utility.
          </Typography>
        </CardContent>
      </Card>
    </Section>

    {/* ------------------------------------------------------------- closing */}
    <Card sx={{ mt: { xs: 6, md: 9 }, backgroundColor: surface.inverse, border: 'none' }}>
      <CardContent sx={{ p: { xs: 3, md: 5 }, textAlign: 'center' }}>
        <Typography variant="h5" sx={{ color: ink.onDark, mb: 1 }}>
          Ready to look at your network?
        </Typography>
        <Typography variant="body2" sx={{ color: ink.onDarkMuted, mb: 3 }}>
          Create an account to upload meter data and start monitoring.
        </Typography>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} justifyContent="center">
          <Button
            component={RouterLink}
            to="/signup"
            variant="contained"
            sx={{ backgroundColor: ink.onDark, color: ink.primary, '&:hover': { backgroundColor: '#f0f0f0' } }}
          >
            Create account
          </Button>
          <Button
            component={RouterLink}
            to="/login"
            variant="outlined"
            sx={{ borderColor: 'rgba(255,255,255,0.35)', color: ink.onDark,
                  '&:hover': { borderColor: ink.onDark, backgroundColor: 'rgba(255,255,255,0.06)' } }}
          >
            Sign in
          </Button>
        </Stack>
      </CardContent>
    </Card>
  </Box>
);

export default LandingPage;
