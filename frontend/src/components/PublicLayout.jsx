import { AppBar, Box, Button, Container, Stack, Toolbar, Typography } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import Footer from './Footer';
import { useAuth } from '../context/AuthContext';
import { ink, line, surface } from '../theme/tokens';

const Mark = ({ size = 24 }) => (
  <Box
    component="svg"
    role="img"
    aria-label="EnergyGuard"
    viewBox="0 0 24 24"
    sx={{ width: size, height: size, color: ink.primary }}
    fill="none"
    stroke="currentColor"
    strokeWidth="1.9"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M13.5 2 5 13h6l-1.5 9L18 11h-6z" />
  </Box>
);

/**
 * Shell for the pages a signed-out visitor can see — currently just the
 * landing page. It carries the same footer as the console, so developer
 * attribution appears on every screen of the site rather than only inside the
 * application.
 */
const PublicLayout = ({ children }) => {
  const { isAuthenticated, user } = useAuth();

  return (
    <Box sx={{ minHeight: '100vh', backgroundColor: surface.page, display: 'flex', flexDirection: 'column' }}>
      <AppBar
        position="sticky"
        elevation={0}
        sx={{ backgroundColor: surface.card, borderBottom: `1px solid ${line.base}` }}
      >
        <Container maxWidth="lg" disableGutters>
          <Toolbar sx={{ gap: 1.25, px: { xs: 2, sm: 3 } }}>
            <Stack
              direction="row"
              spacing={1}
              alignItems="center"
              component={RouterLink}
              to="/"
              sx={{ textDecoration: 'none' }}
            >
              <Mark />
              <Typography variant="subtitle1" sx={{ fontWeight: 700, color: ink.primary }}>
                EnergyGuard
              </Typography>
            </Stack>

            <Box sx={{ flexGrow: 1 }} />

            {isAuthenticated ? (
              <Stack direction="row" spacing={1.25} alignItems="center">
                <Typography variant="body2" sx={{ color: ink.secondary, display: { xs: 'none', sm: 'block' } }}>
                  {user?.full_name}
                </Typography>
                <Button component={RouterLink} to="/dashboard" variant="contained" size="small">
                  Open console
                </Button>
              </Stack>
            ) : (
              <Stack direction="row" spacing={1}>
                <Button component={RouterLink} to="/login" size="small" variant="text">
                  Sign in
                </Button>
                <Button component={RouterLink} to="/signup" size="small" variant="contained">
                  Get started
                </Button>
              </Stack>
            )}
          </Toolbar>
        </Container>
      </AppBar>

      <Container maxWidth="lg" sx={{ flexGrow: 1, py: { xs: 3, md: 4 } }}>
        {children}
        <Footer />
      </Container>
    </Box>
  );
};

export default PublicLayout;
