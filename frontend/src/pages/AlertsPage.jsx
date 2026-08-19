import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Container,
  Divider,
  Grid,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useCallback, useEffect, useState } from 'react';
import ErrorBoundary from '../components/ErrorBoundary';
import { getAlertHistory, getAlertStatus, sendTestAlert } from '../services/api';

const StatusRow = ({ label, value, help }) => (
  <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ py: 1 }}>
    <Tooltip title={help || ''} placement="right">
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
    </Tooltip>
    <Box>{value}</Box>
  </Stack>
);

const BoolChip = ({ value, trueLabel = 'Yes', falseLabel = 'No' }) => (
  <Chip
    size="small"
    color={value ? 'success' : 'default'}
    variant={value ? 'filled' : 'outlined'}
    label={value ? trueLabel : falseLabel}
    sx={{ fontWeight: 700 }}
  />
);

const STATUS_COLORS = { sent: 'success', failed: 'error', cooldown: 'default' };

const AlertsPage = () => {
  const [status, setStatus] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // The token lives in component state only for as long as the page is open.
  // It is never written to localStorage and never baked into the build.
  const [token, setToken] = useState('');
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [statusResponse, historyResponse] = await Promise.all([getAlertStatus(), getAlertHistory()]);
      setStatus(statusResponse.data);
      setHistory(Array.isArray(historyResponse?.data?.alerts) ? historyResponse.data.alerts : []);
      setError('');
    } catch (err) {
      setError(err?.response?.data?.message || err?.message || 'Unable to load alert configuration.');
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const response = await sendTestAlert(token);
      setTestResult({ severity: 'success', message: response?.data?.message || 'Test SMS sent successfully' });
      load();
    } catch (err) {
      const message = err?.response?.data?.message || err?.message || 'Test SMS failed.';
      setTestResult({ severity: err?.response?.status === 429 ? 'warning' : 'error', message });
    } finally {
      setTesting(false);
    }
  };

  return (
    <ErrorBoundary>
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Stack spacing={3}>
          <Box>
            <Typography variant="h4" fontWeight={700}>
              SMS Alerts
            </Typography>
            <Typography color="text.secondary" sx={{ mt: 1 }}>
              Check that theft alerts can reach your phone, and review every alert the backend has attempted.
            </Typography>
          </Box>

          {loading ? (
            <Box display="flex" justifyContent="center" py={6}>
              <CircularProgress />
            </Box>
          ) : error ? (
            <Alert severity="error">{error}</Alert>
          ) : (
            <>
              <Grid container spacing={3}>
                <Grid item xs={12} md={6}>
                  <Card sx={{ height: '100%' }}>
                    <CardContent>
                      <Stack direction="row" justifyContent="space-between" alignItems="center">
                        <Typography variant="h6" fontWeight={700}>
                          Configuration
                        </Typography>
                        <Button size="small" startIcon={<RefreshIcon />} onClick={load}>
                          Refresh
                        </Button>
                      </Stack>

                      {status?.ready ? (
                        <Alert severity="success" sx={{ mt: 2 }}>
                          Alerting is ready. Theft predictions will send an SMS.
                        </Alert>
                      ) : (
                        <Alert severity="warning" sx={{ mt: 2 }}>
                          {status?.configuration_error ||
                            'Alerting is not fully configured. Check backend/.env against .env.example.'}
                        </Alert>
                      )}

                      <Divider sx={{ my: 2 }} />

                      <StatusRow label="Alerting enabled" value={<BoolChip value={status?.enabled} />} />
                      <StatusRow
                        label="Provider"
                        value={<Chip size="small" label={status?.provider || 'unknown'} sx={{ fontWeight: 700 }} />}
                      />
                      <StatusRow
                        label="Provider credentials"
                        value={<BoolChip value={status?.provider_configured} trueLabel="Configured" falseLabel="Missing" />}
                      />
                      <StatusRow
                        label="Destination numbers configured"
                        help="Only the count is shown. Phone numbers never leave the backend."
                        value={<Chip size="small" label={status?.recipients_configured ?? 0} />}
                      />
                      <StatusRow
                        label="Cooldown per meter"
                        help="ALERT_COOLDOWN_MINUTES"
                        value={<Chip size="small" label={`${status?.cooldown_minutes ?? 0} min`} />}
                      />
                      <StatusRow
                        label="Max individual SMS per upload"
                        help="MAX_ALERTS_PER_BATCH"
                        value={<Chip size="small" label={status?.max_alerts_per_batch ?? 0} />}
                      />
                      <StatusRow label="Batch summary SMS" value={<BoolChip value={status?.batch_summary_enabled} />} />
                      <StatusRow
                        label="Test endpoint"
                        help="Requires ALERT_TEST_TOKEN to be set in backend/.env"
                        value={<BoolChip value={status?.test_endpoint_enabled} trueLabel="Enabled" falseLabel="Disabled" />}
                      />
                    </CardContent>
                  </Card>
                </Grid>

                <Grid item xs={12} md={6}>
                  <Card sx={{ height: '100%' }}>
                    <CardContent>
                      <Typography variant="h6" fontWeight={700}>
                        Send a test SMS
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                        Sends one message to the configured number(s) without needing a theft prediction. Paste the
                        ALERT_TEST_TOKEN value from your backend <code>.env</code> file. It is used for this request
                        only and is never saved by the browser.
                      </Typography>

                      <Stack spacing={2} sx={{ mt: 3 }}>
                        <TextField
                          label="Alert test token"
                          type="password"
                          size="small"
                          fullWidth
                          value={token}
                          autoComplete="off"
                          onChange={(event) => setToken(event.target.value)}
                          disabled={!status?.test_endpoint_enabled}
                        />
                        <Button
                          variant="contained"
                          startIcon={<SendIcon />}
                          onClick={handleTest}
                          disabled={testing || !token || !status?.test_endpoint_enabled}
                        >
                          {testing ? 'Sending...' : 'Send test SMS'}
                        </Button>

                        {!status?.test_endpoint_enabled && (
                          <Alert severity="info">
                            Set <code>ALERT_TEST_TOKEN</code> in <code>backend/.env</code> and restart the backend to
                            enable this button.
                          </Alert>
                        )}

                        {testResult && <Alert severity={testResult.severity}>{testResult.message}</Alert>}

                        <Alert severity="info" variant="outlined">
                          Test messages are throttled server-side, so repeated clicks cannot spam your phone.
                        </Alert>
                      </Stack>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>

              <Card>
                <CardContent>
                  <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }} flexWrap="wrap" useFlexGap>
                    <Typography variant="h6" fontWeight={700} sx={{ mr: 1 }}>
                      Alert log
                    </Typography>
                    <Chip size="small" color="success" label={`Sent: ${status?.counts?.sent ?? 0}`} />
                    <Chip size="small" color="error" label={`Failed: ${status?.counts?.failed ?? 0}`} />
                    <Chip size="small" label={`Cooldown blocked: ${status?.counts?.cooldown ?? 0}`} />
                  </Stack>

                  {history.length === 0 ? (
                    <Alert severity="info">No alerts have been attempted yet.</Alert>
                  ) : (
                    <TableContainer sx={{ maxHeight: 460, borderRadius: 3, border: '1px solid', borderColor: 'divider' }}>
                      <Table stickyHeader size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>Meter ID</TableCell>
                            <TableCell>Type</TableCell>
                            <TableCell>Provider</TableCell>
                            <TableCell>Status</TableCell>
                            <TableCell>Confidence</TableCell>
                            <TableCell>Recipients</TableCell>
                            <TableCell>Time</TableCell>
                            <TableCell>Error</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {history.map((entry, index) => (
                            <TableRow hover key={`${entry.meter_id}-${entry.created_at}-${index}`}>
                              <TableCell>{entry.meter_id}</TableCell>
                              <TableCell>{entry.alert_type}</TableCell>
                              <TableCell>{entry.channel || '-'}</TableCell>
                              <TableCell>
                                <Chip
                                  size="small"
                                  color={STATUS_COLORS[entry.status] || 'default'}
                                  label={entry.status}
                                  sx={{ fontWeight: 700 }}
                                />
                              </TableCell>
                              <TableCell>
                                {typeof entry.confidence === 'number' ? `${entry.confidence}%` : '-'}
                              </TableCell>
                              <TableCell>{entry.recipients ?? 0}</TableCell>
                              <TableCell>{entry.created_at}</TableCell>
                              <TableCell sx={{ maxWidth: 320 }}>
                                <Typography variant="caption" color="error.main">
                                  {entry.error || ''}
                                </Typography>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </Stack>
      </Container>
    </ErrorBoundary>
  );
};

export default AlertsPage;
