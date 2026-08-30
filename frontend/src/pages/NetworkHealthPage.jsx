import { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  IconButton,
  MenuItem,
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
import CloseIcon from '@mui/icons-material/Close';
import BoltIcon from '@mui/icons-material/Bolt';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import CurrencyRupeeIcon from '@mui/icons-material/CurrencyRupee';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { getNetworkKpis, getTransformerDetail, getTransformers } from '../services/api';

// Status colours match the MUI theme palette so the page feels native.
const STATUS_COLOUR = {
  CRITICAL: '#f16465',
  WATCH: '#f5a623',
  NORMAL: '#34d399',
  NO_DATA: '#8892ac',
};

const STATUS_LABEL = {
  CRITICAL: 'Critical',
  WATCH: 'Watch',
  NORMAL: 'Normal',
  NO_DATA: 'No data',
};

const PRIORITY_COLOUR = { HIGH: '#f16465', MEDIUM: '#f5a623', LOW: '#8892ac' };

const formatUnits = (value) =>
  Number(value || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 });

const formatRupees = (value) => {
  const amount = Number(value || 0);
  if (amount >= 10000000) return `₹${(amount / 10000000).toFixed(2)} Cr`;
  if (amount >= 100000) return `₹${(amount / 100000).toFixed(2)} L`;
  return `₹${amount.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
};

const StatusChip = ({ status }) => (
  <Chip
    size="small"
    label={STATUS_LABEL[status] || status}
    sx={{
      fontWeight: 700,
      color: STATUS_COLOUR[status],
      backgroundColor: `${STATUS_COLOUR[status]}22`,
      border: `1px solid ${STATUS_COLOUR[status]}55`,
    }}
  />
);

const KpiCard = ({ icon, label, value, sub, colour }) => (
  <Card sx={{ height: '100%' }}>
    <CardContent>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
        <Box sx={{ color: colour || 'primary.main', display: 'flex' }}>{icon}</Box>
        <Typography variant="body2" color="text.secondary">
          {label}
        </Typography>
      </Stack>
      <Typography variant="h4" sx={{ color: colour || 'text.primary' }}>
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

/**
 * Detail view for one transformer.
 *
 * Three things an engineer actually needs: how the loss has moved over the
 * window, how supplied compares with billed day by day, and which meters under
 * this transformer the model has already flagged.
 */
const TransformerDetailDialog = ({ transformerId, days, onClose }) => {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!transformerId) return undefined;
    let cancelled = false;
    setLoading(true);
    setError('');

    getTransformerDetail(transformerId, days)
      .then((response) => {
        if (!cancelled) setDetail(response.data);
      })
      .catch((err) => {
        if (!cancelled) setError(err?.response?.data?.message || err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [transformerId, days]);

  const summary = detail?.summary;
  const trend = (detail?.trend || []).map((point) => ({
    ...point,
    date: point.reading_date?.slice(5),
  }));

  return (
    <Dialog open={Boolean(transformerId)} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle sx={{ pr: 6 }}>
        <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap">
          <Typography variant="h6">{transformerId}</Typography>
          {summary && <StatusChip status={summary.status} />}
          {summary && (
            <Typography variant="body2" color="text.secondary">
              {summary.name} · {summary.area} · {summary.capacity_kva} kVA ·{' '}
              {summary.meter_count} meters
            </Typography>
          )}
        </Stack>
        <IconButton onClick={onClose} sx={{ position: 'absolute', right: 12, top: 12 }}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent dividers>
        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress />
          </Box>
        )}

        {error && <Alert severity="error">{error}</Alert>}

        {!loading && !error && summary && (
          <Stack spacing={3}>
            <Grid container spacing={2}>
              <Grid item xs={6} md={3}>
                <KpiCard
                  icon={<BoltIcon />}
                  label="Supplied"
                  value={formatUnits(summary.energy_supplied)}
                  sub="units into the transformer"
                />
              </Grid>
              <Grid item xs={6} md={3}>
                <KpiCard
                  icon={<BoltIcon />}
                  label="Billed"
                  value={formatUnits(summary.energy_billed)}
                  sub="units billed to consumers"
                  colour="#22d3ee"
                />
              </Grid>
              <Grid item xs={6} md={3}>
                <KpiCard
                  icon={<WarningAmberIcon />}
                  label="Loss"
                  value={`${summary.loss_pct}%`}
                  sub={`${formatUnits(summary.loss_units)} units unaccounted`}
                  colour={STATUS_COLOUR[summary.status]}
                />
              </Grid>
              <Grid item xs={6} md={3}>
                <KpiCard
                  icon={<CurrencyRupeeIcon />}
                  label="Revenue at risk"
                  value={formatRupees(summary.estimated_monthly_revenue_loss)}
                  sub="per month at current loss"
                  colour="#f5a623"
                />
              </Grid>
            </Grid>

            <Alert
              severity={
                summary.status === 'CRITICAL'
                  ? 'error'
                  : summary.status === 'WATCH'
                  ? 'warning'
                  : 'success'
              }
              icon={false}
            >
              Loss exceeded the {summary.loss_pct >= 0 ? '8%' : '8%'} technical limit on{' '}
              <strong>
                {summary.days_above_threshold} of {summary.days_monitored} days
              </strong>
              {summary.persistent
                ? ' — this is a persistent gap, not a one-off reading error.'
                : ' — not persistent enough to confirm; keep monitoring.'}
              {summary.trend === 'worsening' && ' The loss is getting worse over the window.'}
              {summary.trend === 'improving' && ' The loss has been improving recently.'}
            </Alert>

            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle1" gutterBottom>
                Daily loss %
              </Typography>
              <Typography variant="caption" color="text.secondary">
                The dashed line is the 8% technical-loss limit. Anything sustained above it is
                energy leaving the network without being billed.
              </Typography>
              <Box sx={{ height: 280, mt: 2 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trend} margin={{ top: 8, right: 16, left: -8, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                    <XAxis dataKey="date" stroke="#8892ac" fontSize={12} />
                    <YAxis stroke="#8892ac" fontSize={12} unit="%" />
                    <RechartsTooltip
                      contentStyle={{
                        background: '#121a2e',
                        border: '1px solid rgba(255,255,255,0.12)',
                        borderRadius: 12,
                      }}
                      formatter={(value) => [`${value}%`, 'Loss']}
                    />
                    <ReferenceLine y={8} stroke="#34d399" strokeDasharray="6 4" />
                    <ReferenceLine y={15} stroke="#f16465" strokeDasharray="6 4" />
                    <Line
                      type="monotone"
                      dataKey="loss_pct"
                      stroke={STATUS_COLOUR[summary.status]}
                      strokeWidth={2.5}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </Box>
            </Paper>

            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle1" gutterBottom>
                Supplied vs billed, per day
              </Typography>
              <Box sx={{ height: 260, mt: 1 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={trend} margin={{ top: 8, right: 16, left: -8, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                    <XAxis dataKey="date" stroke="#8892ac" fontSize={12} />
                    <YAxis stroke="#8892ac" fontSize={12} />
                    <RechartsTooltip
                      contentStyle={{
                        background: '#121a2e',
                        border: '1px solid rgba(255,255,255,0.12)',
                        borderRadius: 12,
                      }}
                    />
                    <Legend />
                    <Bar dataKey="energy_supplied" name="Supplied" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="energy_billed" name="Billed" fill="#22d3ee" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Box>
            </Paper>

            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle1" gutterBottom>
                Meters flagged by the model under this transformer
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Priority blends the model's confidence with this transformer's loss signal. A meter
                the model dislikes, under a transformer that is provably losing energy, is a far
                stronger case than either signal on its own.
              </Typography>
              {detail.flagged_meters?.length ? (
                <TableContainer sx={{ mt: 2, maxHeight: 320 }}>
                  <Table size="small" stickyHeader>
                    <TableHead>
                      <TableRow>
                        <TableCell>Meter</TableCell>
                        <TableCell>Model says</TableCell>
                        <TableCell align="right">Model confidence</TableCell>
                        <TableCell align="right">DT signal</TableCell>
                        <TableCell align="right">Priority score</TableCell>
                        <TableCell>Priority</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {detail.flagged_meters.map((meter) => (
                        <TableRow key={meter.meter_id} hover>
                          <TableCell>{meter.meter_id}</TableCell>
                          <TableCell>{meter.prediction}</TableCell>
                          <TableCell align="right">{(meter.ml_score * 100).toFixed(0)}%</TableCell>
                          <TableCell align="right">{(meter.dt_score * 100).toFixed(0)}%</TableCell>
                          <TableCell align="right">{meter.priority_score}</TableCell>
                          <TableCell>
                            <Chip
                              size="small"
                              label={meter.priority}
                              sx={{
                                fontWeight: 700,
                                color: PRIORITY_COLOUR[meter.priority],
                                backgroundColor: `${PRIORITY_COLOUR[meter.priority]}22`,
                                border: `1px solid ${PRIORITY_COLOUR[meter.priority]}55`,
                              }}
                            />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Alert severity="info" sx={{ mt: 2 }}>
                  No meters under this transformer have been through the model yet. Upload a CSV
                  containing these meter IDs to see them ranked here.
                </Alert>
              )}
            </Paper>
          </Stack>
        )}
      </DialogContent>
    </Dialog>
  );
};

const NetworkHealthPage = () => {
  const [kpis, setKpis] = useState(null);
  const [rows, setRows] = useState([]);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [seeded, setSeeded] = useState(true);
  const [selected, setSelected] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [kpiResponse, listResponse] = await Promise.all([
        getNetworkKpis(days),
        getTransformers(days),
      ]);
      setKpis(kpiResponse.data);
      setRows(listResponse.data.transformers || []);
      setSeeded(listResponse.data.seeded !== false);
    } catch (err) {
      setError(err?.response?.data?.message || err.message);
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Box>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        justifyContent="space-between"
        alignItems={{ xs: 'flex-start', sm: 'center' }}
        spacing={2}
        sx={{ mb: 3 }}
      >
        <Box>
          <Typography variant="h4">Network Health</Typography>
          <Typography variant="body2" color="text.secondary">
            Energy sent through each distribution transformer versus energy billed under it. A
            persistent gap is theft.
          </Typography>
        </Box>
        <TextField
          select
          size="small"
          label="Window"
          value={days}
          onChange={(event) => setDays(Number(event.target.value))}
          sx={{ minWidth: 140 }}
        >
          <MenuItem value={7}>Last 7 days</MenuItem>
          <MenuItem value={30}>Last 30 days</MenuItem>
          <MenuItem value={60}>Last 60 days</MenuItem>
        </TextField>
      </Stack>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {!loading && !error && !seeded && (
        <Alert severity="info" sx={{ mb: 3 }}>
          No network data yet. Run <code>python seed_transformers.py</code> in the backend folder to
          generate the distribution network and its readings.
        </Alert>
      )}

      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      )}

      {!loading && kpis && (
        <>
          <Grid container spacing={2} sx={{ mb: 3 }}>
            <Grid item xs={12} sm={6} md={3}>
              <KpiCard
                icon={<BoltIcon />}
                label="Transformers monitored"
                value={kpis.total_transformers}
                sub={`${formatUnits(kpis.total_meters)} consumer meters`}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <KpiCard
                icon={<WarningAmberIcon />}
                label="Need investigation"
                value={kpis.critical_count}
                sub={`${kpis.watch_count} more on the watch list`}
                colour={STATUS_COLOUR.CRITICAL}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <KpiCard
                icon={<TrendingUpIcon />}
                label="Average network loss"
                value={`${kpis.avg_loss_pct}%`}
                sub={`technical limit is ${kpis.technical_loss_threshold}%`}
                colour={
                  kpis.avg_loss_pct > kpis.suspicious_loss_threshold
                    ? STATUS_COLOUR.CRITICAL
                    : kpis.avg_loss_pct > kpis.technical_loss_threshold
                    ? STATUS_COLOUR.WATCH
                    : STATUS_COLOUR.NORMAL
                }
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <KpiCard
                icon={<CurrencyRupeeIcon />}
                label="Revenue at risk"
                value={formatRupees(kpis.estimated_monthly_revenue_loss)}
                sub="per month across the network"
                colour="#f5a623"
              />
            </Grid>
          </Grid>

          <Paper sx={{ p: 2 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
              <Typography variant="subtitle1">Inspection priority list</Typography>
              <Typography variant="caption" color="text.secondary">
                Sorted worst first · click a row for detail
              </Typography>
            </Stack>
            <Divider sx={{ mb: 1 }} />
            <TableContainer sx={{ maxHeight: 560 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>Transformer</TableCell>
                    <TableCell>Area</TableCell>
                    <TableCell align="right">Supplied</TableCell>
                    <TableCell align="right">Billed</TableCell>
                    <TableCell align="right">Loss %</TableCell>
                    <TableCell align="center">Days over limit</TableCell>
                    <TableCell align="right">Meters</TableCell>
                    <TableCell align="right">₹ / month</TableCell>
                    <TableCell>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rows.map((row) => (
                    <TableRow
                      key={row.transformer_id}
                      hover
                      onClick={() => setSelected(row.transformer_id)}
                      sx={{ cursor: 'pointer' }}
                    >
                      <TableCell sx={{ fontWeight: 600 }}>
                        {row.transformer_id}
                        {row.trend === 'worsening' && (
                          <Tooltip title="Loss is getting worse over this window">
                            <TrendingUpIcon
                              fontSize="inherit"
                              sx={{ ml: 0.75, color: STATUS_COLOUR.CRITICAL, verticalAlign: 'middle' }}
                            />
                          </Tooltip>
                        )}
                      </TableCell>
                      <TableCell>{row.area}</TableCell>
                      <TableCell align="right">{formatUnits(row.energy_supplied)}</TableCell>
                      <TableCell align="right">{formatUnits(row.energy_billed)}</TableCell>
                      <TableCell
                        align="right"
                        sx={{ fontWeight: 700, color: STATUS_COLOUR[row.status] }}
                      >
                        {row.loss_pct}%
                      </TableCell>
                      <TableCell align="center">
                        <Typography variant="caption" color="text.secondary">
                          {row.days_above_threshold}/{row.days_monitored}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">{row.meter_count}</TableCell>
                      <TableCell align="right">
                        {row.status === 'NORMAL'
                          ? '—'
                          : formatRupees(row.estimated_monthly_revenue_loss)}
                      </TableCell>
                      <TableCell>
                        <StatusChip status={row.status} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </>
      )}

      <TransformerDetailDialog
        transformerId={selected}
        days={days}
        onClose={() => setSelected(null)}
      />
    </Box>
  );
};

export default NetworkHealthPage;
