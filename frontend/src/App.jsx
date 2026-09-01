import { Box, CssBaseline } from '@mui/material';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import { motion } from 'framer-motion';
import { useMemo, useState } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import Footer from './components/Footer';
import ProtectedRoute from './components/ProtectedRoute';
import PublicLayout from './components/PublicLayout';
import Sidebar, { RAIL_GAP, RAIL_WIDTH } from './components/Sidebar';
import { AuthProvider } from './context/AuthContext';
import AlertsPage from './pages/AlertsPage';
import AssistantPage from './pages/AssistantPage';
import DashboardPage from './pages/DashboardPage';
import HistoryPage from './pages/HistoryPage';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import MeterSearchPage from './pages/MeterSearchPage';
import NetworkHealthPage from './pages/NetworkHealthPage';
import SignupPage from './pages/SignupPage';
import UploadPage from './pages/UploadPage';
import { ink, line, radius, status, surface } from './theme/tokens';

// The rail floats clear of the edge, so the layout offset is the rail width
// plus the gap on either side of it.
const RAIL_OFFSET = RAIL_WIDTH + RAIL_GAP * 2;

/**
 * Light monochrome console theme.
 *
 * Every colour comes from theme/tokens.js. Chromatic values appear only where
 * they carry meaning — theft, watch, normal. Everything else is black, white
 * and grey.
 */
const theme = createTheme({
  palette: {
    mode: 'light',
    // "Primary" is black: on a white console the emphatic action is a black
    // pill button, not a coloured one.
    primary: { main: ink.primary, contrastText: ink.onDark },
    secondary: { main: ink.secondary, contrastText: ink.onDark },
    success: { main: status.ok },
    error: { main: status.danger },
    warning: { main: status.warning },
    info: { main: ink.secondary },
    background: { default: surface.page, paper: surface.card },
    text: { primary: ink.primary, secondary: ink.secondary, disabled: ink.muted },
    divider: line.base,
  },
  shape: { borderRadius: radius.md },
  typography: {
    fontFamily: "'Inter', 'Segoe UI', system-ui, sans-serif",
    h1: { fontWeight: 700, letterSpacing: '-0.03em' },
    h2: { fontWeight: 700, letterSpacing: '-0.03em' },
    h3: { fontWeight: 700, letterSpacing: '-0.02em' },
    h4: { fontWeight: 700, letterSpacing: '-0.02em', fontSize: '1.75rem' },
    h5: { fontWeight: 700, letterSpacing: '-0.02em' },
    h6: { fontWeight: 700, letterSpacing: '-0.01em' },
    subtitle1: { fontWeight: 600 },
    subtitle2: { fontWeight: 600 },
    overline: { letterSpacing: '0.08em', fontWeight: 600, fontSize: '0.66rem' },
    button: { textTransform: 'none', fontWeight: 600 },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: surface.page,
          // Figures in KPI tiles must not jitter as they update.
          fontVariantNumeric: 'tabular-nums',
        },
        // A visible focus ring on every interactive element — keyboard users
        // must always be able to see where they are.
        '*:focus-visible': { outline: `2px solid ${ink.primary}`, outlineOffset: '2px' },
        '::-webkit-scrollbar': { width: 10, height: 10 },
        '::-webkit-scrollbar-track': { background: 'transparent' },
        '::-webkit-scrollbar-thumb': { background: line.strong, borderRadius: 999 },
        '::-webkit-scrollbar-thumb:hover': { background: ink.muted },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          backgroundColor: surface.card,
          border: `1px solid ${line.base}`,
          boxShadow: 'none',
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: radius.lg,
          backgroundColor: surface.card,
          border: `1px solid ${line.base}`,
          boxShadow: 'none',
          transition: 'border-color 0.15s ease',
          '&:hover': { borderColor: line.strong },
        },
      },
    },
    MuiCardContent: { styleOverrides: { root: { padding: 20, '&:last-child': { paddingBottom: 20 } } } },
    MuiButton: {
      styleOverrides: {
        root: { borderRadius: radius.pill, paddingInline: 18, boxShadow: 'none' },
        contained: { boxShadow: 'none', '&:hover': { boxShadow: 'none' } },
        containedPrimary: {
          backgroundColor: ink.primary,
          color: ink.onDark,
          '&:hover': { backgroundColor: '#000000' },
        },
        outlined: {
          borderColor: line.strong,
          color: ink.primary,
          '&:hover': { borderColor: ink.primary, backgroundColor: surface.hover },
        },
        text: { color: ink.secondary, '&:hover': { color: ink.primary, backgroundColor: surface.hover } },
        sizeSmall: { paddingInline: 14 },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { borderRadius: radius.pill, fontWeight: 600 },
        outlined: { borderColor: line.strong },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: { borderBottom: `1px solid ${line.subtle}` },
        head: {
          backgroundColor: surface.sunken,
          color: ink.secondary,
          fontWeight: 600,
          fontSize: '0.72rem',
          letterSpacing: '0.05em',
          textTransform: 'uppercase',
        },
      },
    },
    MuiTableRow: { styleOverrides: { root: { '&:hover': { backgroundColor: surface.hover } } } },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          backgroundColor: surface.sunken,
          borderRadius: radius.pill,
          '& .MuiOutlinedInput-notchedOutline': { borderColor: line.base },
          '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: line.strong },
          '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: ink.primary, borderWidth: 1 },
        },
      },
    },
    MuiInputLabel: { styleOverrides: { root: { color: ink.muted } } },
    MuiAlert: {
      styleOverrides: {
        root: { borderRadius: radius.md, border: `1px solid ${line.base}`, backgroundColor: surface.sunken },
        standardError: { borderColor: 'rgba(192,57,43,0.35)' },
        standardWarning: { borderColor: 'rgba(150,105,10,0.35)' },
        standardSuccess: { borderColor: 'rgba(46,125,50,0.35)' },
      },
    },
    MuiDialog: { styleOverrides: { paper: { borderRadius: radius.xl } } },
    MuiTooltip: {
      styleOverrides: {
        tooltip: { backgroundColor: ink.primary, color: ink.onDark, fontSize: '0.75rem', borderRadius: radius.sm },
        arrow: { color: ink.primary },
      },
    },
    MuiLinearProgress: {
      styleOverrides: { root: { backgroundColor: line.base, borderRadius: 999 }, bar: { backgroundColor: ink.primary } },
    },
    MuiCircularProgress: { styleOverrides: { root: { color: ink.primary } } },
    MuiDivider: { styleOverrides: { root: { borderColor: line.subtle } } },
    MuiTab: {
      styleOverrides: {
        root: { textTransform: 'none', fontWeight: 600, color: ink.muted, '&.Mui-selected': { color: ink.primary } },
      },
    },
    MuiTabs: { styleOverrides: { indicator: { backgroundColor: ink.primary, height: 2 } } },
  },
});

/**
 * The signed-in application: navigation rail, routed page, footer.
 *
 * Mounted behind ProtectedRoute, so none of these pages render for a visitor
 * without a valid session.
 */
const ConsoleLayout = () => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const year = useMemo(() => new Date().getFullYear(), []);
  const location = useLocation();

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', backgroundColor: surface.page }}>
      <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} onOpen={() => setMobileOpen(true)} />

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          minWidth: 0,                              // lets wide tables scroll instead of pushing the page
          ml: { md: `${RAIL_OFFSET}px` },
          width: { md: `calc(100% - ${RAIL_OFFSET}px)` },
          display: 'flex',
          flexDirection: 'column',
          px: { xs: 1.5, sm: 2, md: 0 },
          pr: { md: 2 },
          py: { xs: 1.5, md: 2 },
        }}
      >
        <Box sx={{ maxWidth: 1560, mx: 'auto', width: '100%', flexGrow: 1 }}>
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
          >
            <Routes>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/upload" element={<UploadPage />} />
              <Route path="/history" element={<HistoryPage />} />
              <Route path="/meters" element={<MeterSearchPage />} />
              <Route path="/network" element={<NetworkHealthPage />} />
              <Route path="/assistant" element={<AssistantPage />} />
              <Route path="/alerts" element={<AlertsPage />} />
              {/* Anything else inside the console falls back to the dashboard,
                  including the retired /model-info path. */}
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </motion.div>
        </Box>
        <Footer year={year} />
      </Box>
    </Box>
  );
};

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AuthProvider>
        <Routes>
          {/* Public */}
          <Route path="/" element={<PublicLayout><LandingPage /></PublicLayout>} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />

          {/* Everything else is the application, and needs a session. */}
          <Route
            path="/*"
            element={(
              <ProtectedRoute>
                <ConsoleLayout />
              </ProtectedRoute>
            )}
          />
        </Routes>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
