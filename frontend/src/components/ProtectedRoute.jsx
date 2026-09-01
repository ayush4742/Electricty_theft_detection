import { Box, CircularProgress, Stack, Typography } from '@mui/material';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ink } from '../theme/tokens';

/**
 * Gate for the application pages.
 *
 * While the stored token is still being resolved it renders a spinner rather
 * than redirecting — otherwise a refresh on /network would bounce a signed-in
 * user to the sign-in screen for a moment before bouncing them back.
 *
 * The attempted path is passed along so sign-in can return the user to where
 * they were going.
 */
const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <Stack alignItems="center" justifyContent="center" spacing={2} sx={{ minHeight: '60vh' }}>
        <CircularProgress size={22} />
        <Typography variant="body2" sx={{ color: ink.muted }}>
          Checking your session…
        </Typography>
      </Stack>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Box>{children}</Box>;
};

export default ProtectedRoute;
