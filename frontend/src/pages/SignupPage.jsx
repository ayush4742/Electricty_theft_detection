import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  CircularProgress,
  FormControlLabel,
  IconButton,
  InputAdornment,
  LinearProgress,
  Link,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import VisibilityIcon from '@mui/icons-material/VisibilityRounded';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOffRounded';
import { Link as RouterLink, Navigate, useNavigate } from 'react-router-dom';
import AuthLayout from '../components/AuthLayout';
import { useAuth } from '../context/AuthContext';
import { ink, status } from '../theme/tokens';

const MIN_PASSWORD = 8;   // matches auth_store.MIN_PASSWORD on the backend

// The server also requires at least one letter and one digit. Mirroring the
// rule here means the user is told before they press the button, not after.
const passwordRuleBroken = (value) => {
  if (value.length < MIN_PASSWORD) return `Use at least ${MIN_PASSWORD} characters.`;
  if (!/[A-Za-z]/.test(value) || !/\d/.test(value)) {
    return 'Include at least one letter and one number.';
  }
  return '';
};

const readError = (err) => {
  if (err?.response?.data?.message) return err.response.data.message;
  if (err?.code === 'ERR_NETWORK') {
    return 'Could not reach the EnergyGuard backend. Check that the Flask server is running on port 5000.';
  }
  return 'Could not create the account. Please try again.';
};

/**
 * A rough strength read-out, shown only as guidance.
 *
 * It is not a security control — the server enforces the real minimum. It
 * exists so a user is not told "too weak" only after pressing the button.
 */
const strengthOf = (value) => {
  if (!value) return { score: 0, label: '', colour: ink.muted };
  let score = 0;
  if (value.length >= MIN_PASSWORD) score += 1;
  if (value.length >= 12) score += 1;
  if (/[a-z]/.test(value) && /[A-Z]/.test(value)) score += 1;
  if (/\d/.test(value)) score += 1;
  if (/[^A-Za-z0-9]/.test(value)) score += 1;
  if (score <= 2) return { score, label: 'Weak', colour: status.danger };
  if (score === 3) return { score, label: 'Fair', colour: status.warning };
  return { score, label: 'Strong', colour: status.ok };
};

const SignupPage = () => {
  const { signup, isAuthenticated, loading: authLoading } = useAuth();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [touched, setTouched] = useState({});

  const strength = useMemo(() => strengthOf(password), [password]);

  if (!authLoading && isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  const emailLooksValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  const mismatch = Boolean(confirm) && confirm !== password;

  const fieldErrors = {
    fullName: touched.fullName && fullName.trim().length < 2 ? 'Enter your full name.' : '',
    email: touched.email && !emailLooksValid ? 'Enter a valid email address.' : '',
    password: touched.password ? passwordRuleBroken(password) : '',
    confirm: mismatch ? 'Passwords do not match.' : '',
  };

  const canSubmit =
    fullName.trim().length >= 2 &&
    emailLooksValid &&
    !passwordRuleBroken(password) &&
    confirm === password &&
    accepted;

  const submit = async (event) => {
    event.preventDefault();
    setTouched({ fullName: true, email: true, password: true, confirm: true });
    setError('');
    if (!canSubmit) {
      setError('Please complete every field before continuing.');
      return;
    }
    setBusy(true);
    try {
      await signup(fullName.trim(), email.trim(), password);
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setError(readError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout
      title="Create your account"
      subtitle="One account per operator. Your password is hashed before it is stored."
      footer={
        <Typography variant="body2" sx={{ color: ink.secondary }}>
          Already registered?{' '}
          <Link component={RouterLink} to="/login" sx={{ color: ink.primary, fontWeight: 600 }}>
            Sign in
          </Link>
        </Typography>
      }
    >
      <Box component="form" onSubmit={submit} noValidate>
        <Stack spacing={2}>
          {error ? <Alert severity="error" role="alert">{error}</Alert> : null}

          <TextField
            label="Full name"
            name="name"
            autoComplete="name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            onBlur={() => setTouched((t) => ({ ...t, fullName: true }))}
            error={Boolean(fieldErrors.fullName)}
            helperText={fieldErrors.fullName}
            fullWidth
            required
            autoFocus
          />

          <TextField
            label="Email"
            type="email"
            name="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onBlur={() => setTouched((t) => ({ ...t, email: true }))}
            error={Boolean(fieldErrors.email)}
            helperText={fieldErrors.email}
            fullWidth
            required
          />

          <Box>
            <TextField
              label="Password"
              type={showPassword ? 'text' : 'password'}
              name="new-password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onBlur={() => setTouched((t) => ({ ...t, password: true }))}
              error={Boolean(fieldErrors.password)}
              helperText={
                fieldErrors.password || `At least ${MIN_PASSWORD} characters, including a letter and a number.`
              }
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
            {password ? (
              <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mt: 1, px: 0.5 }}>
                <LinearProgress
                  variant="determinate"
                  value={Math.min(100, (strength.score / 5) * 100)}
                  sx={{ flexGrow: 1, height: 4, '& .MuiLinearProgress-bar': { backgroundColor: strength.colour } }}
                  aria-hidden="true"
                />
                <Typography variant="caption" sx={{ color: strength.colour, fontWeight: 600, minWidth: 44 }}>
                  {strength.label}
                </Typography>
              </Stack>
            ) : null}
          </Box>

          <TextField
            label="Confirm password"
            type={showPassword ? 'text' : 'password'}
            name="confirm-password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            error={Boolean(fieldErrors.confirm)}
            helperText={fieldErrors.confirm}
            fullWidth
            required
          />

          <FormControlLabel
            control={<Checkbox checked={accepted} onChange={(e) => setAccepted(e.target.checked)} size="small" />}
            label={
              <Typography variant="body2" sx={{ color: ink.secondary }}>
                I understand this is an academic project and will use it with data I am
                permitted to analyse.
              </Typography>
            }
            sx={{ alignItems: 'flex-start', '& .MuiCheckbox-root': { pt: 0.25 } }}
          />

          <Button
            type="submit"
            variant="contained"
            size="large"
            disabled={busy}
            startIcon={busy ? <CircularProgress size={16} sx={{ color: ink.onDark }} /> : null}
            sx={{ py: 1.15 }}
          >
            {busy ? 'Creating account…' : 'Create account'}
          </Button>
        </Stack>
      </Box>
    </AuthLayout>
  );
};

export default SignupPage;
