import { Box, Stack, Typography } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { ink, line, radius, surface } from '../theme/tokens';

/**
 * Shared frame for the sign-in and sign-up screens.
 *
 * Two panels on desktop: a black brand panel carrying the wordmark and a short,
 * accurate description of what the system does, and a white card holding the
 * form. On a phone the brand panel collapses to a single header line so the
 * form is the first thing in reach.
 *
 * Nothing here claims a capability the project does not have — the bullet list
 * describes the pipeline that actually exists.
 */

const Mark = ({ size = 26, colour }) => (
  <Stack direction="row" spacing={0.25} alignItems="center" sx={{ color: colour || ink.onDark }}>
    <Box
      component="svg"
      role="img"
      aria-label="EnergyGuard"
      viewBox="0 0 24 24"
      sx={{ width: size, height: size }}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M13.5 2 5 13h6l-1.5 9L18 11h-6z" />
    </Box>
    <Box sx={{ width: 5, height: 5, borderRadius: '50%', backgroundColor: 'currentColor', mt: 1.2 }} />
  </Stack>
);

const POINTS = [
  'Score uploaded consumption data for theft risk',
  'Compare transformer supply against billed units',
  'Search any meter and read its full history',
  'Ask the assistant questions about your own data',
];

const AuthLayout = ({ title, subtitle, children, footer }) => (
  <Box
    sx={{
      minHeight: '100vh',
      backgroundColor: surface.page,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      p: { xs: 1.5, sm: 3 },
    }}
  >
    <Box
      sx={{
        width: '100%',
        maxWidth: 980,
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', md: '0.9fr 1.1fr' },
        borderRadius: `${radius.xl}px`,
        overflow: 'hidden',
        border: `1px solid ${line.base}`,
        backgroundColor: surface.card,
      }}
    >
      {/* Brand panel */}
      <Box
        sx={{
          backgroundColor: surface.rail,
          color: ink.onDark,
          p: { xs: 2.5, md: 4 },
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
        }}
      >
        <Stack direction="row" spacing={1} alignItems="center">
          <Mark />
          <Typography variant="h6" sx={{ fontWeight: 700, color: ink.onDark }}>
            EnergyGuard
          </Typography>
        </Stack>

        <Box sx={{ display: { xs: 'none', md: 'block' } }}>
          <Typography variant="h5" sx={{ color: ink.onDark, mt: 2, lineHeight: 1.25 }}>
            Electricity theft detection &amp; network monitoring
          </Typography>
          <Typography variant="body2" sx={{ color: ink.onDarkMuted, mt: 1.5 }}>
            A machine-learning pipeline for consumption data, paired with a
            transformer-level energy balance check.
          </Typography>

          <Stack spacing={1.25} sx={{ mt: 3 }}>
            {POINTS.map((point) => (
              <Stack key={point} direction="row" spacing={1.25} alignItems="flex-start">
                <Box
                  aria-hidden="true"
                  sx={{
                    width: 5,
                    height: 5,
                    borderRadius: '50%',
                    backgroundColor: ink.onDarkMuted,
                    mt: '7px',
                    flexShrink: 0,
                  }}
                />
                <Typography variant="body2" sx={{ color: ink.onDarkMuted }}>
                  {point}
                </Typography>
              </Stack>
            ))}
          </Stack>

          <Box sx={{ flexGrow: 1 }} />
          <Typography variant="caption" sx={{ color: ink.onDarkMuted, display: 'block', mt: 4 }}>
            Final-year project · Federated Learning Edition
          </Typography>
        </Box>
      </Box>

      {/* Form panel */}
      <Box sx={{ p: { xs: 2.5, sm: 4 } }}>
        <Typography variant="h5" sx={{ color: ink.primary }}>
          {title}
        </Typography>
        {subtitle ? (
          <Typography variant="body2" sx={{ color: ink.secondary, mt: 0.75 }}>
            {subtitle}
          </Typography>
        ) : null}

        <Box sx={{ mt: 3 }}>{children}</Box>

        {footer ? <Box sx={{ mt: 2.5 }}>{footer}</Box> : null}

        <Typography variant="caption" sx={{ color: ink.muted, display: 'block', mt: 3 }}>
          <Box component={RouterLink} to="/" sx={{ color: ink.secondary, textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}>
            ← Back to home
          </Box>
        </Typography>
      </Box>
    </Box>
  </Box>
);

export default AuthLayout;
