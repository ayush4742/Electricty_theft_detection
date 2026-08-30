import { Box, CssBaseline } from '@mui/material';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import { motion } from 'framer-motion';
import { useMemo, useState } from 'react';
import { Route, Routes } from 'react-router-dom';
import Footer from './components/Footer';
import Sidebar from './components/Sidebar';
import AlertsPage from './pages/AlertsPage';
import DashboardPage from './pages/DashboardPage';
import HistoryPage from './pages/HistoryPage';
import ModelInfoPage from './pages/ModelInfoPage';
import NetworkHealthPage from './pages/NetworkHealthPage';
import AssistantPage from './pages/AssistantPage';
import UploadPage from './pages/UploadPage';

const drawerWidth = 240;

const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: '#8b5cf6' },
    secondary: { main: '#22d3ee' },
    success: { main: '#34d399' },
    error: { main: '#f16465' },
    warning: { main: '#f5a623' },
    background: {
      default: '#0b1020',
      paper: '#121a2e',
    },
    text: {
      primary: '#f4f6fb',
      secondary: '#8892ac',
    },
    divider: 'rgba(255,255,255,0.08)',
  },
  shape: { borderRadius: 4 },
  typography: {
    fontFamily: "'Inter', 'Segoe UI', sans-serif",
    h1: { fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700 },
    h2: { fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700 },
    h3: { fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700 },
    h4: { fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700 },
    h5: { fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700 },
    h6: { fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700 },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          background:
            'radial-gradient(circle at 14% 8%, rgba(139,92,246,0.14), transparent 30%), radial-gradient(circle at 88% 4%, rgba(34,211,238,0.10), transparent 26%), #0b1020',
          backgroundAttachment: 'fixed',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          border: '1px solid rgba(255,255,255,0.08)',
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 16,
          boxShadow: '0 20px 50px rgba(0,0,0,0.35)',
          transition: 'transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease',
          '&:hover': {
            transform: 'translateY(-3px)',
            boxShadow: '0 26px 64px rgba(0,0,0,0.45)',
            borderColor: 'rgba(139,92,246,0.3)',
          },
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: { textTransform: 'none', fontWeight: 600, borderRadius: 12 },
        containedPrimary: {
          backgroundImage: 'linear-gradient(135deg, #8b5cf6, #22d3ee)',
          boxShadow: '0 14px 32px rgba(139,92,246,0.25)',
          '&:hover': { backgroundImage: 'linear-gradient(135deg, #7c3aed, #06b6d4)' },
        },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          borderRadius: 14,
          '&.Mui-selected': {
            backgroundImage: 'linear-gradient(135deg, rgba(139,92,246,0.9), rgba(34,211,238,0.65))',
            boxShadow: '0 10px 24px rgba(139,92,246,0.35)',
          },
        },
      },
    },
  },
});

function App() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: 'flex', minHeight: '100vh' }}>
        <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
        <Box sx={{ flexGrow: 1, width: { md: `calc(100% - ${drawerWidth}px)` }, ml: { md: `${drawerWidth}px` } }}>
          <Box sx={{ px: { xs: 2, md: 3 }, py: 3, maxWidth: '1400px', mx: 'auto' }}>
            <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
              <Routes>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/upload" element={<UploadPage />} />
                <Route path="/history" element={<HistoryPage />} />
                <Route path="/network" element={<NetworkHealthPage />} />
                <Route path="/assistant" element={<AssistantPage />} />
                <Route path="/alerts" element={<AlertsPage />} />
                <Route path="/model-info" element={<ModelInfoPage />} />
              </Routes>
            </motion.div>
          </Box>
          <Footer />
        </Box>
      </Box>
    </ThemeProvider>
  );
}

export default App;