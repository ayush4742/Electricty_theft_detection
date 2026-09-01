import { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  FormControlLabel,
  IconButton,
  InputAdornment,
  Link,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import VisibilityIcon from '@mui/icons-material/VisibilityRounded';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOffRounded';
import { Link as RouterLink, Navigate, useLocation, useNavigate } from 'react-router-dom';
import AuthLayout from '../components/AuthLayout';
import { useAuth } from '../context/AuthContext';
import { getAuthStatus } from '../services/api';
import { ink } from '../theme/tokens';

/** Turn an axios failure into something a person can act on. */
const readError = (err) => {
  if (err?.response?.data?.message) return err.response.data.message;
  if (err?.code === 'ERR_NETWORK') {
    return 'Could not reach the EnergyGuard backend. Check that the Flask server is running on port 5000.';
  }
  return 'Sign in failed. Please try again.';
};

const LoginPage = () => {
  const { login, isAuthenticated, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [accounts, setAccounts] = useState(null);   // null = not known yet
  const [forgotOpen, setForgotOpen] = useState(false);

  // Lets the screen say "no accounts yet" on a fresh install instead of
  // presenting a sign-in form nobody can satisfy.
  useEffect(() => {
    let cancelled = false;
    getAuthStatus()
      .then(({ data }) => { if (!cancelled) setAccounts(data.accounts); })
      .catch(() => { /* backend down; the sign-in attempt will say so */ });
    return () => { cancelled = true; };
  }, []);

  if (!authLoading && isAuthenticated) {
    return <Navigate to={location.state?.from || '/dashboard'} replace />;
  }

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    if (!email.trim() || !password) {
      setError('Enter your email and password.');
      return;
    }
    setBusy(true);
    try {
      await login(email.trim(), password, remember);
      navigate(location.state?.from || '/dashboard', { replace: true });
    } catch (err) {
      setError(readError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to open the monitoring console."
      footer={
        <Typography variant="body2" sx={{ color: ink.secondary }}>
          New here?{' '}
          <Link component={RouterLink} to="/signup" sx={{ color: ink.primary, fontWeight: 600 }}>
            Create an account
          </Link>
        </Typography>
      }
    >
      <Box component="form" onSubmit={submit} noValidate>
        <Stack spacing={2}>
          {accounts === 0 ? (
            <Alert severity="info">
              No accounts exist yet. <Link component={RouterLink} to="/signup">Create the first one</Link>.
            </Alert>
          ) : null}

          {error ? <Alert severity="error" role="alert">{error}</Alert> : null}

          <TextField
            label="Email"
            type="email"
            name="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            fullWidth
            required
            autoFocus
            inputProps={{ 'aria-label': 'Email address' }}
          />

          <TextField
            label="Password"
            type={showPassword ? 'text' : 'password'}
            name="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            fullWidth
            required
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    onClick={() => setShowPassword((v) => !v)}
                    edge="end"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    aria-pressed={showPassword}
                  >
                    {showPassword ? <VisibilityOffIcon fontSize="small" /> : <VisibilityIcon fontSize="small" />}
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />

          <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ flexWrap: 'wrap' }}>
            <FormControlLabel
              control={<Checkbox checked={remember} onChange={(e) => setRemember(e.target.checked)} size="small" />}
              label={<Typography variant="body2" sx={{ color: ink.secondary }}>Remember me for 30 days</Typography>}
            />
            <Link
              component="button"
              type="button"
              variant="body2"
              onClick={() => setForgotOpen(true)}
              sx={{ color: ink.secondary }}
            >
              Forgot password?
            </Link>
          </Stack>

          <Button
            type="submit"
            variant="contained"
            size="large"
            disabled={busy}
            startIcon={busy ? <CircularProgress size={16} sx={{ color: ink.onDark }} /> : null}
            sx={{ py: 1.15 }}
          >
            {busy ? 'Signing in…' : 'Sign in'}
          </Button>
        </Stack>
      </Box>

      {/* Honest about scope: there is no mail service in this project, so there
          is no self-service reset. Saying so beats a button that does nothing. */}
      <Dialog open={forgotOpen} onClose={() => setForgotOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>Password reset</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ color: ink.secondary }}>
            EnergyGuard does not send email, so there is no automated reset link. An
            administrator with access to the server can reset a password directly in
            the application database, or you can create a new account.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setForgotOpen(false)}>Close</Button>
          <Button variant="contained" component={RouterLink} to="/signup" onClick={() => setForgotOpen(false)}>
            Create account
          </Button>
        </DialogActions>
      </Dialog>
    </AuthLayout>
  );
};

export default LoginPage;
