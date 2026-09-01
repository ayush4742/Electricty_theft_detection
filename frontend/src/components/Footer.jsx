import { Box, Divider, Stack, Typography } from '@mui/material';
import { ink, line, radius, surface } from '../theme/tokens';

/**
 * Global footer. Rendered once per shell — inside the console layout and inside
 * the public layout — so it appears on every screen and there is exactly one of
 * it on any given page.
 */

const DEVELOPERS = ['Umme Salma', 'Nishant Kumar Rai', 'Ayush Kumar', 'Kotla HimaSree'];

const Footer = ({ year = new Date().getFullYear() }) => (
  <Box
    component="footer"
    sx={{
      mt: 3,
      px: { xs: 2, sm: 3 },
      py: 2.25,
      backgroundColor: surface.card,
      border: `1px solid ${line.base}`,
      borderRadius: `${radius.lg}px`,
    }}
  >
    <Stack
      direction={{ xs: 'column', md: 'row' }}
      spacing={{ xs: 1.5, md: 2 }}
      justifyContent="space-between"
      alignItems={{ xs: 'flex-start', md: 'center' }}
    >
      <Box>
        <Typography variant="body2" sx={{ color: ink.primary, fontWeight: 600 }}>
          © {year} EnergyGuard. All rights reserved.
        </Typography>
        <Typography variant="caption" sx={{ color: ink.secondary }}>
          AI-Based Electricity Theft Detection &amp; Monitoring System
        </Typography>
      </Box>

      <Box sx={{ textAlign: { xs: 'left', md: 'right' } }}>
        <Typography variant="caption" sx={{ color: ink.muted, display: 'block', mb: 0.25 }}>
          Developed by
        </Typography>
        <Stack
          direction="row"
          spacing={1}
          alignItems="center"
          flexWrap="wrap"
          useFlexGap
          justifyContent={{ xs: 'flex-start', md: 'flex-end' }}
          divider={
            <Divider
              orientation="vertical"
              flexItem
              aria-hidden="true"
              sx={{ borderColor: line.base }}
            />
          }
        >
          {DEVELOPERS.map((name) => (
            <Typography key={name} variant="caption" sx={{ color: ink.secondary, fontWeight: 600 }}>
              {name}
            </Typography>
          ))}
        </Stack>
        <Typography variant="caption" sx={{ color: ink.muted, display: 'block', mt: 0.5 }}>
          Federated Learning Edition
        </Typography>
      </Box>
    </Stack>
  </Box>
);

export default Footer;
