import {
  Alert,
  Box,
  Button,
  ButtonGroup,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Snackbar,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import { useCallback, useEffect, useMemo, useState } from 'react';
import AlertStatusChip from '../components/AlertStatusChip';
import AlertSummaryBanner from '../components/AlertSummaryBanner';
import ErrorBoundary from '../components/ErrorBoundary';
import UploadArea from '../components/UploadArea';
import { getLatestUpload, predictCsv } from '../services/api';
import { ink, line, status, statusFill, surface } from '../theme/tokens';

const EMPTY_STATS = {
  totalRows: 0, theftCount: 0, normalCount: 0, processingTime: 0, averageConfidence: 0,
};

const UploadPage = () => {
  const [acceptedFiles, setAcceptedFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [restoring, setRestoring] = useState(true);
  const [results, setResults] = useState([]);
  const [stats, setStats] = useState(EMPTY_STATS);
  const [batch, setBatch] = useState(null);          // persisted upload metadata
  const [error, setError] = useState('');
  const [alertSummary, setAlertSummary] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '' });
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [startNew, setStartNew] = useState(false);

  /**
   * Restore the last upload from the server when the page mounts.
   *
   * This is the fix for the state-loss bug. React Router unmounts this route on
   * navigation, so anything held only in component state is gone when the user
   * comes back. The backend already stored every scored row in `predictions`;
   * what it lacked was a record of the RUN. `GET /uploads/latest` now returns
   * that record plus its rows, read by id range.
   *
   * This is a read. It does not re-upload, does not re-run the model, and
   * creates no records - the same request could be made a hundred times with no
   * effect on the database.
   */
  useEffect(() => {
    let cancelled = false;
    getLatestUpload()
      .then((response) => {
        const restored = response?.data?.batch;
        if (cancelled || !restored) return;
        const rows = Array.isArray(restored.results) ? restored.results : [];
        setBatch(restored);
        setResults(rows);
        setAlertSummary(restored.alert_summary || null);
        setStats({
          totalRows: Number(restored.total_rows || rows.length || 0),
          theftCount: Number(restored.theft_count || 0),
          normalCount: Number(restored.normal_count || 0),
          processingTime: Number(restored.processing_seconds || 0),
          averageConfidence: Number(restored.average_confidence || 0),
        });
      })
      .catch(() => {
        /* No stored upload, or the endpoint is unavailable. Either way the page
           simply opens empty - this must never block uploading a new file. */
      })
      .finally(() => {
        if (!cancelled) setRestoring(false);
      });
    return () => { cancelled = true; };
  }, []);

  const handleUpload = useCallback(async (file) => {
    if (!file) {
      setSnackbar({ open: true, message: 'Choose a CSV file first.' });
      return;
    }

    const formData = new FormData();
    formData.append('file', file);
    setLoading(true);
    setError('');
    setResults([]);
    setAlertSummary(null);
    setBatch(null);
    setStats(EMPTY_STATS);
    setPage(0);

    const startedAt = window?.performance ? window.performance.now() : Date.now();

    try {
      const response = await predictCsv(formData);
      const rows = Array.isArray(response?.data?.results) ? response.data.results : [];
      const totalRows = Number(response?.data?.total_predictions ?? rows.length ?? 0);
      const theftCount = rows.filter((r) => r?.prediction === 'Theft').length;
      const averageConfidence = rows.length
        ? rows.reduce((sum, r) => sum + (typeof r?.confidence === 'number' ? r.confidence : 0), 0) / rows.length
        : 0;
      const processingTime = ((window?.performance ? window.performance.now() : Date.now()) - startedAt) / 1000;
      const summary = response?.data?.alert_summary || null;

      setResults(rows);
      setAlertSummary(summary);
      setStats({ totalRows, theftCount, normalCount: totalRows - theftCount, processingTime, averageConfidence });
      setBatch({
        filename: file.name,
        uploaded_at: new Date().toLocaleString(),
        total_rows: totalRows,
        status: 'completed',
        // Marked so the banner can say "just uploaded" rather than "restored".
        _fresh: true,
      });
      setStartNew(false);

      const sent = Number(summary?.alerts_sent || 0);
      const failed = Number(summary?.alerts_failed || 0);
      setSnackbar({
        open: true,
        message: failed > 0
          ? `Prediction complete. ${failed} SMS alert(s) failed.`
          : sent > 0
            ? `Prediction complete. ${sent} SMS alert(s) sent.`
            : 'Prediction complete.',
      });
    } catch (err) {
      const message = err?.response?.data?.message || err?.response?.data?.error || err?.message || 'CSV upload failed.';
      setResults([]);
      setAlertSummary(null);
      setStats(EMPTY_STATS);
      setError(message);
      setSnackbar({ open: true, message });
    } finally {
      setLoading(false);
    }
  }, []);

  const filteredResults = useMemo(() => {
    const term = search.trim().toLowerCase();
    return results.filter((r) => {
      const prediction = typeof r?.prediction === 'string' ? r.prediction : 'Unknown';
      const meterId = typeof r?.meter_id === 'string' ? r.meter_id : '';
      const matchesFilter =
        filter === 'theft' ? prediction === 'Theft' : filter === 'normal' ? prediction === 'Normal' : true;
      return matchesFilter && (!term || meterId.toLowerCase().includes(term));
    });
  }, [filter, results, search]);

  const pagedResults = useMemo(
    () => filteredResults.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage),
    [filteredResults, page, rowsPerPage],
  );

  const handleExport = () => {
    if (!results.length) return;
    const rows = [
      ['Meter ID', 'Prediction', 'Risk', 'Confidence', 'Timestamp', 'SMS Alert'],
      ...results.map((r) => [
        r?.meter_id || 'N/A',
        r?.prediction || 'Unknown',
        r?.risk || 'Unknown',
        typeof r?.confidence === 'number' ? `${r.confidence}%` : 'N/A',
        r?.timestamp || 'N/A',
        r?.alert_sent ? 'Sent' : r?.alert_error ? 'Failed' : 'Not sent',
      ]),
    ];
    const blob = new Blob([rows.map((r) => r.join(',')).join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'prediction-results.csv';
    link.click();
    URL.revokeObjectURL(url);
  };

  const hasUpload = Boolean(batch) && stats.totalRows > 0;
  const showUploader = !hasUpload || startNew;

  const StatCell = ({ label, value, colour }) => (
    <Box sx={{ flex: '1 1 140px', minWidth: 130, px: 2, py: 1.75 }}>
      <Typography variant="overline" sx={{ color: ink.muted, display: 'block' }}>{label}</Typography>
      <Typography variant="h5" sx={{ color: colour || ink.primary, mt: 0.25 }}>{value}</Typography>
    </Box>
  );

  return (
    <ErrorBoundary>
      <Stack spacing={3}>
        <Box>
          <Typography variant="h4">CSV Upload</Typography>
          <Typography variant="body2" sx={{ color: ink.secondary, mt: 0.75 }}>
            Score a batch of meter readings for suspected theft. Results are stored on the server, so
            this page restores your last run when you return to it.
          </Typography>
        </Box>

        {restoring && (
          <Stack direction="row" spacing={1.5} alignItems="center" sx={{ color: ink.muted }}>
            <CircularProgress size={15} />
            <Typography variant="body2">Checking for a previous upload…</Typography>
          </Stack>
        )}

        {/* --- persisted upload status ------------------------------------ */}
        {!restoring && hasUpload && (
          <Card>
            <CardContent sx={{ pb: '16px !important' }}>
              <Stack
                direction={{ xs: 'column', md: 'row' }}
                spacing={2}
                justifyContent="space-between"
                alignItems={{ xs: 'flex-start', md: 'center' }}
              >
                <Stack direction="row" spacing={1.75} alignItems="center" sx={{ minWidth: 0 }}>
                  <DescriptionOutlinedIcon sx={{ color: ink.secondary }} />
                  <Box sx={{ minWidth: 0 }}>
                    <Typography variant="subtitle1" sx={{ wordBreak: 'break-all' }}>
                      {batch.filename || 'uploaded.csv'}
                    </Typography>
                    <Typography variant="caption" sx={{ color: ink.muted }}>
                      {batch._fresh ? 'Uploaded just now' : 'Restored from server'}
                      {batch.uploaded_at ? ` · ${batch.uploaded_at}` : ''}
                    </Typography>
                  </Box>
                </Stack>

                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                  <Chip
                    size="small"
                    icon={<CheckCircleOutlineIcon />}
                    label="Upload complete"
                    sx={{ color: status.ok, backgroundColor: statusFill.ok, '& .MuiChip-icon': { color: status.ok } }}
                  />
                  <Chip size="small" variant="outlined" label="Validated" />
                  <Chip size="small" variant="outlined" label="Prediction complete" />
                  <Tooltip title="Clears this view only. Stored predictions are never deleted.">
                    <Button size="small" startIcon={<RestartAltIcon />} onClick={() => setStartNew(true)}>
                      Upload new CSV
                    </Button>
                  </Tooltip>
                </Stack>
              </Stack>

              <Divider sx={{ my: 2 }} />

              <Stack
                direction="row"
                flexWrap="wrap"
                divider={<Divider orientation="vertical" flexItem sx={{ borderColor: line.subtle }} />}
                sx={{ mx: -2 }}
              >
                <StatCell label="Records" value={stats.totalRows.toLocaleString('en-IN')} />
                <StatCell label="Theft flagged" value={stats.theftCount.toLocaleString('en-IN')} colour={status.danger} />
                <StatCell label="Normal" value={stats.normalCount.toLocaleString('en-IN')} colour={status.ok} />
                <StatCell label="Avg confidence" value={`${Number(stats.averageConfidence).toFixed(1)}%`} />
                <StatCell label="Processing" value={`${Number(stats.processingTime).toFixed(2)}s`} />
              </Stack>
            </CardContent>
          </Card>
        )}

        {/* --- uploader --------------------------------------------------- */}
        {!restoring && showUploader && (
          <Box>
            {hasUpload && (
              <Alert severity="info" sx={{ mb: 2 }}>
                Uploading a new file replaces the view below. Previous predictions stay in Prediction History.
                <Button size="small" onClick={() => setStartNew(false)} sx={{ ml: 1 }}>Cancel</Button>
              </Alert>
            )}
            <UploadArea
              loading={loading}
              acceptedFiles={acceptedFiles}
              setAcceptedFiles={setAcceptedFiles}
              onUpload={handleUpload}
            />
          </Box>
        )}

        {error && <Alert severity="error">{error}</Alert>}
        {stats.theftCount > 0 && (
          <Alert severity="warning">
            {stats.theftCount} meter{stats.theftCount === 1 ? '' : 's'} flagged for inspection in this batch.
          </Alert>
        )}
        <AlertSummaryBanner summary={alertSummary} />

        {/* --- results ----------------------------------------------------- */}
        {loading ? (
          <Stack alignItems="center" spacing={1.5} sx={{ py: 6 }}>
            <CircularProgress />
            <Typography variant="body2" sx={{ color: ink.muted }}>Scoring meters…</Typography>
          </Stack>
        ) : (
          <Card>
            <CardContent>
              {results.length === 0 ? (
                <Alert severity="info">
                  {restoring ? 'Loading…' : 'No predictions yet. Upload a CSV to begin.'}
                </Alert>
              ) : (
                <>
                  <Stack
                    direction={{ xs: 'column', md: 'row' }}
                    spacing={1.5}
                    sx={{ mb: 2.5 }}
                    alignItems={{ xs: 'stretch', md: 'center' }}
                  >
                    <TextField
                      label="Search meter ID"
                      size="small"
                      fullWidth
                      value={search}
                      onChange={(e) => { setSearch(e.target.value); setPage(0); }}
                      inputProps={{ 'aria-label': 'Search results by meter ID' }}
                    />
                    <ButtonGroup size="small" aria-label="Filter predictions">
                      {[['all', 'All'], ['theft', 'Theft'], ['normal', 'Normal']].map(([key, label]) => (
                        <Button
                          key={key}
                          variant={filter === key ? 'contained' : 'outlined'}
                          onClick={() => { setFilter(key); setPage(0); }}
                          aria-pressed={filter === key}
                        >
                          {label}
                        </Button>
                      ))}
                    </ButtonGroup>
                    <Button variant="outlined" startIcon={<DownloadIcon />} onClick={handleExport}>
                      Export
                    </Button>
                  </Stack>

                  <TableContainer sx={{ maxHeight: 480, border: `1px solid ${line.base}`, borderRadius: 1 }}>
                    <Table stickyHeader size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Meter ID</TableCell>
                          <TableCell>Prediction</TableCell>
                          <TableCell>Risk</TableCell>
                          <TableCell align="right">Confidence</TableCell>
                          <TableCell>Timestamp</TableCell>
                          <TableCell>SMS alert</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {pagedResults.map((result, index) => {
                          const prediction = result?.prediction || 'Unknown';
                          const risk = result?.risk || 'Unknown';
                          const isTheft = prediction === 'Theft';
                          const riskColour =
                            risk === 'High' ? status.danger : risk === 'Medium' ? status.warning : status.ok;
                          const meterId = result?.meter_id || `Row ${index + 1}`;

                          return (
                            <TableRow hover key={`${meterId}-${index}`}>
                              <TableCell sx={{ fontFamily: 'monospace', fontSize: 12, wordBreak: 'break-all' }}>
                                {meterId}
                              </TableCell>
                              <TableCell>
                                <Chip
                                  size="small"
                                  label={prediction}
                                  sx={{
                                    fontWeight: 600,
                                    color: isTheft ? status.danger : status.ok,
                                    backgroundColor: isTheft ? statusFill.danger : statusFill.ok,
                                  }}
                                />
                              </TableCell>
                              <TableCell sx={{ color: riskColour, fontWeight: 600 }}>{risk}</TableCell>
                              <TableCell align="right">
                                {typeof result?.confidence === 'number' ? `${result.confidence}%` : 'N/A'}
                              </TableCell>
                              <TableCell sx={{ color: ink.secondary, whiteSpace: 'nowrap' }}>
                                {result?.timestamp || 'N/A'}
                              </TableCell>
                              <TableCell>
                                <AlertStatusChip
                                  alertSent={result?.alert_sent}
                                  alertError={result?.alert_error}
                                  alertSkipped={result?.alert_skipped}
                                  prediction={prediction}
                                />
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </TableContainer>

                  <TablePagination
                    component="div"
                    count={filteredResults.length}
                    page={page}
                    onPageChange={(_, next) => setPage(next)}
                    rowsPerPage={rowsPerPage}
                    onRowsPerPageChange={(e) => { setRowsPerPage(parseInt(e.target.value, 10)); setPage(0); }}
                    rowsPerPageOptions={[10, 25, 50]}
                  />
                </>
              )}
            </CardContent>
          </Card>
        )}

        <Snackbar
          open={snackbar.open}
          autoHideDuration={4000}
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          message={snackbar.message}
        />
      </Stack>
    </ErrorBoundary>
  );
};

export default UploadPage;
