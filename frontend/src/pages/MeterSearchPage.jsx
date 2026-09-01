import { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Grid,
  InputAdornment,
  Paper,
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
import SearchIcon from '@mui/icons-material/Search';
import BoltIcon from '@mui/icons-material/Bolt';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import ElectricalServicesIcon from '@mui/icons-material/ElectricalServices';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { getMeterProfile, searchMeters } from '../services/api';

const VERDICT_COLOUR = { theft: '#c0392b', normal: '#2e7d32' };
const RISK_COLOUR = { high: '#c0392b', medium: '#96690a', low: '#2e7d32' };
const FLAG_COLOUR = { warning: '#96690a', info: '#6e6e6e', ok: '#2e7d32' };
const STATUS_COLOUR = { CRITICAL: '#c0392b', WATCH: '#96690a', NORMAL: '#2e7d32' };

const verdictColour = (value) => VERDICT_COLOUR[String(value || '').toLowerCase()] || '#8a8a8a';
const riskColour = (value) => RISK_COLOUR[String(value || '').toLowerCase()] || '#8a8a8a';

const Stat = ({ label, value, sub, colour }) => (
  <Card sx={{ height: '100%' }}>
    <CardContent sx={{ py: 2 }}>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="h5" sx={{ color: colour || 'text.primary', mt: 0.5 }}>
        {value}
      </Typography>
      {sub && (
        <Typography variant="caption" color="text.secondary">
          {sub}
        </Typography>
      )}
    </CardContent>
  </Card>
);

const FlagRow = ({ flag }) => {
  const Icon =
    flag.level === 'warning'
      ? WarningAmberIcon
      : flag.level === 'ok'
      ? CheckCircleOutlineIcon
      : InfoOutlinedIcon;
  return (
    <Stack direction="row" spacing={1.5} alignItems="flex-start">
      <Icon sx={{ fontSize: 20, color: FLAG_COLOUR[flag.level], mt: 0.2 }} />
      <Box>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {flag.label}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {flag.detail}
        </Typography>
      </Box>
    </Stack>
  );
};

const MeterSearchPage = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [selected, setSelected] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Debounced search, so typing a 32-character meter id does not fire 32 requests.
  useEffect(() => {
    setSearching(true);
    const timer = setTimeout(() => {
      searchMeters(query, 25)
        .then((response) => setResults(response.data.meters || []))
        .catch((err) => setError(err?.response?.data?.message || err.message))
        .finally(() => setSearching(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  const open = useCallback((meterId) => {
    setSelected(meterId);
    setLoading(true);
    setError('');
    setProfile(null);
    getMeterProfile(meterId)
      .then((response) => setProfile(response.data))
      .catch((err) => setError(err?.response?.data?.message || err.message))
      .finally(() => setLoading(false));
  }, []);

  const stats = profile?.consumption?.stats;
  const series = profile?.consumption?.series || [];

  return (
    <Box>
      <Typography variant="h4">Meter Lookup</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Search any meter from your uploaded data to see its full record — the model&apos;s verdict,
        its consumption history, and the transformer that feeds it.
      </Typography>

      <TextField
        fullWidth
        placeholder="Type any part of a meter ID, e.g. 057600C6 or the full 32-character id"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">
              <SearchIcon />
            </InputAdornment>
          ),
          endAdornment: searching ? <CircularProgress size={16} /> : null,
          sx: { borderRadius: 3 },
        }}
        sx={{ mb: 2 }}
      />

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* ---------------- results list ---------------- */}
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 1.5, maxHeight: 620, overflowY: 'auto' }}>
            <Typography variant="caption" color="text.secondary" sx={{ px: 1 }}>
              {query ? `${results.length} match${results.length === 1 ? '' : 'es'}` : 'Recently analysed'}
            </Typography>
            <Divider sx={{ my: 1 }} />
            {results.length === 0 && !searching ? (
              <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
                No meter matches that. Only meters present in an uploaded CSV appear here.
              </Typography>
            ) : (
              <Stack spacing={0.5}>
                {results.map((row) => (
                  <Box
                    key={row.meter_id}
                    onClick={() => open(row.meter_id)}
                    sx={{
                      px: 1.5,
                      py: 1,
                      borderRadius: 2,
                      cursor: 'pointer',
                      border: '1px solid',
                      borderColor:
                        selected === row.meter_id ? 'primary.main' : 'transparent',
                      backgroundColor:
                        selected === row.meter_id ? 'rgba(242,242,242,0.12)' : 'transparent',
                      '&:hover': { backgroundColor: 'rgba(0,0,0,0.03)' },
                    }}
                  >
                    <Typography
                      variant="body2"
                      sx={{ fontFamily: 'monospace', fontSize: 12, wordBreak: 'break-all' }}
                    >
                      {row.meter_id}
                    </Typography>
                    <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 0.5 }}>
                      <Chip
                        size="small"
                        label={row.prediction}
                        sx={{
                          height: 18,
                          fontSize: 10,
                          fontWeight: 700,
                          color: verdictColour(row.prediction),
                          backgroundColor: `${verdictColour(row.prediction)}22`,
                        }}
                      />
                      <Typography variant="caption" color="text.secondary">
                        {row.confidence}% · {row.times_analysed}× analysed
                      </Typography>
                    </Stack>
                  </Box>
                ))}
              </Stack>
            )}
          </Paper>
        </Grid>

        {/* ---------------- profile ---------------- */}
        <Grid item xs={12} md={8}>
          {loading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
              <CircularProgress />
            </Box>
          )}

          {!loading && !profile && (
            <Paper sx={{ p: 6, textAlign: 'center' }}>
              <SearchIcon sx={{ fontSize: 40, color: 'text.secondary', mb: 1 }} />
              <Typography variant="body2" color="text.secondary">
                Pick a meter on the left to see its full record.
              </Typography>
            </Paper>
          )}

          {!loading && profile && (
            <Stack spacing={2.5}>
              <Paper sx={{ p: 2.5 }}>
                <Typography
                  variant="h6"
                  sx={{ fontFamily: 'monospace', fontSize: 15, wordBreak: 'break-all' }}
                >
                  {profile.meter_id}
                </Typography>
                <Stack direction="row" spacing={1} sx={{ mt: 1.5, flexWrap: 'wrap', gap: 1 }}>
                  <Chip
                    label={profile.latest.prediction}
                    sx={{
                      fontWeight: 700,
                      color: verdictColour(profile.latest.prediction),
                      backgroundColor: `${verdictColour(profile.latest.prediction)}22`,
                      border: `1px solid ${verdictColour(profile.latest.prediction)}55`,
                    }}
                  />
                  <Chip
                    label={`${profile.latest.confidence}% confidence`}
                    variant="outlined"
                    size="small"
                  />
                  <Chip
                    label={`${profile.latest.risk} risk`}
                    size="small"
                    sx={{
                      color: riskColour(profile.latest.risk),
                      backgroundColor: `${riskColour(profile.latest.risk)}22`,
                    }}
                  />
                  <Chip
                    label={`Analysed ${profile.times_analysed}×`}
                    size="small"
                    variant="outlined"
                  />
                  {profile.verdict_changed && (
                    <Tooltip title="The model reached different verdicts on different uploads for this meter">
                      <Chip label="Verdict changed" size="small" color="warning" variant="outlined" />
                    </Tooltip>
                  )}
                </Stack>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5 }}>
                  First analysed {profile.first_analysed} · last {profile.last_analysed}
                </Typography>
              </Paper>

              {stats?.readings > 0 && (
                <>
                  <Grid container spacing={2}>
                    <Grid item xs={6} sm={3}>
                      <Stat
                        label="Readings on record"
                        value={stats.readings.toLocaleString('en-IN')}
                        sub={
                          stats.missing_readings
                            ? `${stats.missing_readings} days missing (${stats.missing_percent}%)`
                            : 'days of consumption'
                        }
                      />
                    </Grid>
                    <Grid item xs={6} sm={3}>
                      <Stat
                        label="Average daily"
                        value={stats.average_daily}
                        sub={`peak ${stats.peak}`}
                      />
                    </Grid>
                    <Grid item xs={6} sm={3}>
                      <Stat
                        label="Zero-usage days"
                        value={stats.zero_days}
                        sub={`longest run ${stats.longest_zero_run} days`}
                        colour={stats.longest_zero_run >= 30 ? '#96690a' : undefined}
                      />
                    </Grid>
                    <Grid item xs={6} sm={3}>
                      <Stat
                        label="Second-half change"
                        value={`${stats.change_percent > 0 ? '+' : ''}${stats.change_percent}%`}
                        sub="vs first half of record"
                        colour={stats.change_percent <= -40 ? '#96690a' : undefined}
                      />
                    </Grid>
                  </Grid>

                  <Paper sx={{ p: 2 }}>
                    <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
                      <BoltIcon fontSize="small" color="primary" />
                      <Typography variant="subtitle1">Consumption history</Typography>
                    </Stack>
                    <Typography variant="caption" color="text.secondary">
                      {stats.readings.toLocaleString('en-IN')} stored readings, averaged into{' '}
                      {series.length} points. The dashed line is this meter&apos;s own average.
                    </Typography>
                    <Box sx={{ height: 260, mt: 2 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={series} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
                          <defs>
                            <linearGradient id="usageFill" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="#111111" stopOpacity={0.55} />
                              <stop offset="100%" stopColor="#111111" stopOpacity={0.03} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.05)" />
                          <XAxis
                            dataKey="index"
                            stroke="#8a8a8a"
                            fontSize={11}
                            tickFormatter={(value) => `D${value}`}
                          />
                          <YAxis stroke="#8a8a8a" fontSize={11} />
                          <RechartsTooltip
                            contentStyle={{
                              background: '#ffffff',
                              border: '1px solid rgba(0,0,0,0.10)',
                              borderRadius: 12,
                            }}
                            labelFormatter={(value) => `Around day ${value}`}
                            formatter={(value, name) => [value, name === 'value' ? 'Average' : name]}
                          />
                          <ReferenceLine
                            y={stats.average_daily}
                            stroke="#6e6e6e"
                            strokeDasharray="6 4"
                          />
                          <Area
                            type="monotone"
                            dataKey="value"
                            stroke="#111111"
                            strokeWidth={2}
                            fill="url(#usageFill)"
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    </Box>
                  </Paper>
                </>
              )}

              {stats?.readings === 0 && (
                <Alert severity="info">
                  No consumption readings were stored with this meter&apos;s predictions, so the
                  usage chart is unavailable. Re-upload the CSV to capture them.
                </Alert>
              )}

              <Paper sx={{ p: 2.5 }}>
                <Typography variant="subtitle1" gutterBottom>
                  What the readings show
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Observations computed from this meter&apos;s stored readings. They describe the
                  usage pattern — they are not a verdict.
                </Typography>
                <Stack spacing={1.75} sx={{ mt: 2 }}>
                  {profile.flags.map((flag, index) => (
                    <FlagRow key={index} flag={flag} />
                  ))}
                </Stack>
              </Paper>

              {profile.transformer && (
                <Paper sx={{ p: 2.5 }}>
                  <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
                    <ElectricalServicesIcon fontSize="small" color="primary" />
                    <Typography variant="subtitle1">Network context</Typography>
                  </Stack>
                  <Grid container spacing={2}>
                    <Grid item xs={6} sm={3}>
                      <Stat
                        label="Transformer"
                        value={profile.transformer.transformer_id}
                        sub={profile.transformer.area}
                      />
                    </Grid>
                    <Grid item xs={6} sm={3}>
                      <Stat
                        label="Transformer loss"
                        value={`${profile.transformer.loss_percent}%`}
                        sub={profile.transformer.status}
                        colour={STATUS_COLOUR[profile.transformer.status]}
                      />
                    </Grid>
                    <Grid item xs={6} sm={3}>
                      <Stat
                        label="Combined priority"
                        value={profile.transformer.priority}
                        sub={`score ${profile.transformer.priority_score}`}
                        colour={
                          profile.transformer.priority === 'HIGH'
                            ? '#c0392b'
                            : profile.transformer.priority === 'MEDIUM'
                            ? '#96690a'
                            : undefined
                        }
                      />
                    </Grid>
                    <Grid item xs={6} sm={3}>
                      <Stat
                        label="Meters on this DT"
                        value={profile.transformer.meters_on_transformer}
                        sub="sharing the same feeder"
                      />
                    </Grid>
                  </Grid>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
                    Priority blends the model&apos;s confidence for this meter with how much energy
                    its transformer is actually losing. Both pointing the same way makes a strong
                    case; the model alone under a healthy transformer usually does not.
                  </Typography>
                </Paper>
              )}

              {profile.history.length > 1 && (
                <Paper sx={{ p: 2 }}>
                  <Typography variant="subtitle1" gutterBottom>
                    Analysis history
                  </Typography>
                  <TableContainer sx={{ maxHeight: 260 }}>
                    <Table size="small" stickyHeader>
                      <TableHead>
                        <TableRow>
                          <TableCell>When</TableCell>
                          <TableCell>Verdict</TableCell>
                          <TableCell align="right">Confidence</TableCell>
                          <TableCell>Risk</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {profile.history.map((row) => (
                          <TableRow key={row.id} hover>
                            <TableCell>{row.timestamp}</TableCell>
                            <TableCell sx={{ color: verdictColour(row.prediction), fontWeight: 600 }}>
                              {row.prediction}
                            </TableCell>
                            <TableCell align="right">{row.confidence}%</TableCell>
                            <TableCell>{row.risk}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Paper>
              )}

              {profile.alerts.length > 0 && (
                <Paper sx={{ p: 2 }}>
                  <Typography variant="subtitle1" gutterBottom>
                    Alerts raised for this meter
                  </Typography>
                  <TableContainer sx={{ maxHeight: 220 }}>
                    <Table size="small" stickyHeader>
                      <TableHead>
                        <TableRow>
                          <TableCell>When</TableCell>
                          <TableCell>Channel</TableCell>
                          <TableCell>Status</TableCell>
                          <TableCell align="right">Recipients</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {profile.alerts.map((row, index) => (
                          <TableRow key={index} hover>
                            <TableCell>{row.created_at}</TableCell>
                            <TableCell>{row.channel || '—'}</TableCell>
                            <TableCell>{row.status}</TableCell>
                            <TableCell align="right">{row.recipients}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Paper>
              )}
            </Stack>
          )}
        </Grid>
      </Grid>
    </Box>
  );
};

export default MeterSearchPage;
