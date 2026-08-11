import {
  Alert,
  Box,
  Button,
  ButtonGroup,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Container,
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
  Typography,
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import { motion } from 'framer-motion';
import { useMemo, useState } from 'react';
import ErrorBoundary from '../components/ErrorBoundary';
import UploadArea from '../components/UploadArea';
import { predictCsv } from '../services/api';

const UploadPage = () => {
  const [acceptedFiles, setAcceptedFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [stats, setStats] = useState({ totalRows: 0, theftCount: 0, normalCount: 0, processingTime: 0, averageConfidence: 0 });
  const [error, setError] = useState('');
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const handleUpload = async (file) => {
    if (!file) {
      setSnackbar({ open: true, message: 'Please choose a CSV file first.', severity: 'error' });
      return;
    }

    const formData = new FormData();
    formData.append('file', file);
    setLoading(true);
    setError('');
    setResults([]);
    setStats({ totalRows: 0, theftCount: 0, normalCount: 0, processingTime: 0, averageConfidence: 0 });
    setPage(0);

    const startedAt = typeof window !== 'undefined' && window.performance ? window.performance.now() : Date.now();

    try {
      const response = await predictCsv(formData);
      const responseResults = Array.isArray(response?.data?.results) ? response.data.results : [];
      const totalRows = Number(response?.data?.total_predictions ?? responseResults.length ?? 0);
      const theftCount = responseResults.filter((item) => item?.prediction === 'Theft').length;
      const normalCount = responseResults.filter((item) => item?.prediction === 'Normal').length;
      const averageConfidence = responseResults.length
        ? responseResults.reduce((sum, item) => sum + (typeof item?.confidence === 'number' ? item.confidence : 0), 0) / responseResults.length
        : 0;
      const processingTime = ((typeof window !== 'undefined' && window.performance ? window.performance.now() : Date.now()) - startedAt) / 1000;

      setResults(responseResults);
      setStats({ totalRows, theftCount, normalCount, processingTime, averageConfidence });
      setSnackbar({ open: true, message: 'Prediction completed successfully.', severity: 'success' });
    } catch (err) {
      const backendMessage = err?.response?.data?.message || err?.response?.data?.error || err?.message || 'CSV upload failed.';
      setResults([]);
      setStats({ totalRows: 0, theftCount: 0, normalCount: 0, processingTime: 0, averageConfidence: 0 });
      setError(backendMessage);
      setSnackbar({ open: true, message: backendMessage, severity: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const filteredResults = useMemo(() => {
    const searchValue = search.trim().toLowerCase();

    return results.filter((result) => {
      const prediction = typeof result?.prediction === 'string' ? result.prediction : 'Unknown';
      const meterId = typeof result?.meter_id === 'string' && result.meter_id ? result.meter_id : '';
      const matchesFilter =
        filter === 'theft' ? prediction === 'Theft' : filter === 'normal' ? prediction === 'Normal' : true;
      const matchesSearch = !searchValue || meterId.toLowerCase().includes(searchValue);

      return matchesFilter && matchesSearch;
    });
  }, [filter, results, search]);

  const pagedResults = useMemo(() => {
    const startIndex = page * rowsPerPage;
    return filteredResults.slice(startIndex, startIndex + rowsPerPage);
  }, [filteredResults, page, rowsPerPage]);

  const handleExport = () => {
    if (!results.length) return;

    const csvRows = [
      ['Meter ID', 'Prediction', 'Risk', 'Confidence', 'Timestamp'],
      ...results.map((result) => [
        typeof result?.meter_id === 'string' && result.meter_id ? result.meter_id : 'N/A',
        typeof result?.prediction === 'string' ? result.prediction : 'Unknown',
        typeof result?.risk === 'string' ? result.risk : 'Unknown',
        typeof result?.confidence === 'number' ? `${result.confidence}%` : 'N/A',
        typeof result?.timestamp === 'string' && result.timestamp ? result.timestamp : 'N/A',
      ]),
    ];

    const csvContent = csvRows.map((row) => row.join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const fileUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = fileUrl;
    link.download = 'prediction-results.csv';
    link.click();
    URL.revokeObjectURL(fileUrl);
  };

  const showWarning = stats.theftCount > 0;

  return (
    <ErrorBoundary>
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Stack spacing={3}>
          <Box>
            <Typography variant="h4" fontWeight={700}>
              CSV Upload
            </Typography>
            <Typography color="text.secondary" sx={{ mt: 1 }}>
              Run high-confidence theft detection over uploaded meter data and review the results in a production-style dashboard.
            </Typography>
          </Box>

          <UploadArea loading={loading} acceptedFiles={acceptedFiles} setAcceptedFiles={setAcceptedFiles} onUpload={handleUpload} />

          {error && <Alert severity="error">{error}</Alert>}
          {showWarning && (
            <Alert severity="warning">
              ⚠ {stats.theftCount} suspicious meters detected. Please review the results.
            </Alert>
          )}

          {stats.totalRows > 0 && (
            <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
              <Card sx={{ borderRadius: 4, border: '1px solid rgba(25, 118, 210, 0.16)', boxShadow: '0 18px 42px rgba(15,23,42,0.08)', background: 'linear-gradient(135deg, rgba(37,99,235,0.06) 0%, rgba(255,255,255,1) 100%)' }}>
                <CardContent>
                  <Stack direction={{ xs: 'column', md: 'row' }} justifyContent="space-between" spacing={2} alignItems={{ xs: 'flex-start', md: 'center' }}>
                    <Box>
                      <Typography variant="h6" fontWeight={700}>
                        Prediction Completed Successfully
                      </Typography>
                      <Typography color="text.secondary" sx={{ mt: 1 }}>
                        A complete prediction run is ready for review.
                      </Typography>
                    </Box>
                    <Chip icon={<CheckCircleOutlineIcon />} label="Live Results" color="primary" sx={{ fontWeight: 700 }} />
                  </Stack>

                  <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ mt: 3 }}>
                    <Box sx={{ flex: 1, p: 2.5, borderRadius: 3, background: 'linear-gradient(135deg, rgba(37,99,235,0.12) 0%, rgba(255,255,255,1) 100%)' }}>
                      <Typography variant="body2" color="text.secondary">Total Processed</Typography>
                      <Typography variant="h5" fontWeight={700} sx={{ mt: 0.5, color: 'primary.main' }}>
                        {stats.totalRows}
                      </Typography>
                    </Box>
                    <Box sx={{ flex: 1, p: 2.5, borderRadius: 3, background: 'linear-gradient(135deg, rgba(220,38,38,0.12) 0%, rgba(255,255,255,1) 100%)' }}>
                      <Typography variant="body2" color="text.secondary">Theft Count</Typography>
                      <Typography variant="h5" fontWeight={700} sx={{ mt: 0.5, color: 'error.main' }}>
                        {stats.theftCount}
                      </Typography>
                    </Box>
                    <Box sx={{ flex: 1, p: 2.5, borderRadius: 3, background: 'linear-gradient(135deg, rgba(22,163,74,0.12) 0%, rgba(255,255,255,1) 100%)' }}>
                      <Typography variant="body2" color="text.secondary">Normal Count</Typography>
                      <Typography variant="h5" fontWeight={700} sx={{ mt: 0.5, color: 'success.main' }}>
                        {stats.normalCount}
                      </Typography>
                    </Box>
                  </Stack>

                  <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ mt: 3 }}>
                    <Box sx={{ flex: 1, p: 2.5, borderRadius: 3, background: 'linear-gradient(135deg, rgba(124,58,237,0.12) 0%, rgba(255,255,255,1) 100%)' }}>
                      <Typography variant="body2" color="text.secondary">Average Confidence</Typography>
                      <Typography variant="h6" fontWeight={700} sx={{ mt: 0.5, color: 'secondary.main' }}>
                        {stats.averageConfidence.toFixed(1)}%
                      </Typography>
                    </Box>
                    <Box sx={{ flex: 1, p: 2.5, borderRadius: 3, background: 'linear-gradient(135deg, rgba(245,158,11,0.14) 0%, rgba(255,255,255,1) 100%)' }}>
                      <Typography variant="body2" color="text.secondary">Processing Time</Typography>
                      <Typography variant="h6" fontWeight={700} sx={{ mt: 0.5, color: 'warning.main' }}>
                        {stats.processingTime.toFixed(2)} seconds
                      </Typography>
                    </Box>
                  </Stack>
                </CardContent>
              </Card>
            </motion.div>
          )}

          {loading ? (
            <Box display="flex" justifyContent="center" py={4}>
              <CircularProgress />
            </Box>
          ) : (
            <Card sx={{ borderRadius: 4, boxShadow: '0 16px 40px rgba(15,23,42,0.08)' }}>
              <CardContent>
                {results.length === 0 ? (
                  <Alert severity="info">No predictions available.</Alert>
                ) : (
                  <>
                    <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ mb: 3 }} alignItems={{ xs: 'stretch', md: 'center' }}>
                      <TextField
                        label="Search Meter ID"
                        size="small"
                        fullWidth
                        value={search}
                        onChange={(event) => {
                          setSearch(event.target.value);
                          setPage(0);
                        }}
                      />
                      <ButtonGroup variant="outlined" color="primary" size="small" aria-label="filter predictions">
                        <Button variant={filter === 'all' ? 'contained' : 'outlined'} onClick={() => { setFilter('all'); setPage(0); }}>
                          Show All
                        </Button>
                        <Button variant={filter === 'theft' ? 'contained' : 'outlined'} onClick={() => { setFilter('theft'); setPage(0); }}>
                          Theft Only
                        </Button>
                        <Button variant={filter === 'normal' ? 'contained' : 'outlined'} onClick={() => { setFilter('normal'); setPage(0); }}>
                          Normal Only
                        </Button>
                      </ButtonGroup>
                      <Button variant="contained" startIcon={<DownloadIcon />} onClick={handleExport}>
                        Export Results
                      </Button>
                    </Stack>

                    <TableContainer sx={{ maxHeight: 480, borderRadius: 3, border: '1px solid', borderColor: 'divider' }}>
                      <Table stickyHeader size="small" sx={{ '& .MuiTableRow-root:nth-of-type(odd)': { backgroundColor: 'rgba(37,99,235,0.03)' } }}>
                        <TableHead>
                          <TableRow>
                            <TableCell>Meter ID</TableCell>
                            <TableCell>Prediction</TableCell>
                            <TableCell>Risk</TableCell>
                            <TableCell>Confidence</TableCell>
                            <TableCell>Timestamp</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {pagedResults.map((result, index) => {
                            const prediction = typeof result?.prediction === 'string' ? result.prediction : 'Unknown';
                            const risk = typeof result?.risk === 'string' ? result.risk : 'Unknown';
                            const confidence = typeof result?.confidence === 'number' ? `${result.confidence}%` : 'N/A';
                            const meterId = typeof result?.meter_id === 'string' && result.meter_id ? result.meter_id : `Row ${index + 1}`;
                            const timestamp = typeof result?.timestamp === 'string' && result.timestamp ? result.timestamp : 'N/A';
                            const chipColor = prediction === 'Theft' ? 'error' : 'success';
                            const riskColor = risk === 'High' ? 'error' : risk === 'Medium' ? 'warning' : 'success';

                            return (
                              <TableRow hover key={`${meterId}-${index}`} sx={{ '&:hover': { backgroundColor: 'rgba(37,99,235,0.06)' } }}>
                                <TableCell>{meterId}</TableCell>
                                <TableCell>
                                  <Chip label={prediction} color={chipColor} size="small" sx={{ fontWeight: 700 }} />
                                </TableCell>
                                <TableCell>
                                  <Chip label={risk} color={riskColor} size="small" sx={{ fontWeight: 700 }} />
                                </TableCell>
                                <TableCell>{confidence}</TableCell>
                                <TableCell>{timestamp}</TableCell>
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
                      onPageChange={(_, nextPage) => setPage(nextPage)}
                      rowsPerPage={rowsPerPage}
                      onRowsPerPageChange={(event) => {
                        setRowsPerPage(parseInt(event.target.value, 10));
                        setPage(0);
                      }}
                      rowsPerPageOptions={[10, 25, 50]}
                    />
                  </>
                )}
              </CardContent>
            </Card>
          )}
        </Stack>

        <Snackbar open={snackbar.open} autoHideDuration={4000} onClose={() => setSnackbar({ ...snackbar, open: false })} message={snackbar.message} />
      </Container>
    </ErrorBoundary>
  );
};

export default UploadPage;
