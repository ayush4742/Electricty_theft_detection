import { Box, Button, Card, CardContent, Chip, FormControl, InputLabel, MenuItem, Paper, Select, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TablePagination, TableRow, TextField, Typography } from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import { useMemo, useState } from 'react';

const HistoryTable = ({ history }) => {
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const safeHistory = Array.isArray(history) ? history.filter((item) => item && typeof item === 'object') : [];

  const filteredHistory = useMemo(() => {
    return safeHistory.filter((item) => {
      const meterId = `${item?.meter_id || ''}`.toLowerCase();
      const prediction = `${item?.prediction || ''}`;
      const matchesSearch = !search || meterId.includes(search.toLowerCase());
      const matchesFilter = filter === 'all' || prediction === filter;
      return matchesSearch && matchesFilter;
    });
  }, [filter, safeHistory, search]);

  const pagedHistory = filteredHistory.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);

  const handleExport = () => {
    const rows = filteredHistory.map((row) => [row?.meter_id || 'N/A', row?.prediction || 'Unknown', row?.risk || 'Unknown', `${row?.confidence ?? 'N/A'}`, row?.timestamp || 'N/A']);
    const csvContent = [['Meter ID', 'Prediction', 'Risk', 'Confidence', 'Timestamp'], ...rows].map((row) => row.join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'prediction-history.csv';
    link.click();
    URL.revokeObjectURL(url);
  };

  if (!safeHistory.length) {
    return (
      <Card sx={{ borderRadius: 4, border: '1px solid', borderColor: 'divider', boxShadow: '0 18px 42px rgba(15,23,42,0.07)' }}>
        <CardContent>
          <Typography color="text.secondary">No prediction history available.</Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card sx={{ borderRadius: 4, border: '1px solid', borderColor: 'divider', boxShadow: '0 18px 42px rgba(15,23,42,0.07)' }}>
      <CardContent>
        <Stack direction={{ xs: 'column', md: 'row' }} justifyContent="space-between" alignItems={{ xs: 'flex-start', md: 'center' }} spacing={2} sx={{ mb: 2 }}>
          <Typography variant="h6" fontWeight={700}>
            Prediction History
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <TextField size="small" label="Search Meter ID" value={search} onChange={(event) => { setSearch(event.target.value); setPage(0); }} />
            <FormControl size="small" sx={{ minWidth: 160 }}>
              <InputLabel>Prediction</InputLabel>
              <Select value={filter} label="Prediction" onChange={(event) => { setFilter(event.target.value); setPage(0); }}>
                <MenuItem value="all">All</MenuItem>
                <MenuItem value="Theft">Theft</MenuItem>
                <MenuItem value="Normal">Normal</MenuItem>
              </Select>
            </FormControl>
            <Button variant="outlined" startIcon={<DownloadIcon />} onClick={handleExport}>
              Export CSV
            </Button>
          </Box>
        </Stack>
        <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 3, maxHeight: 480 }}>
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
              {pagedHistory.map((row, index) => {
                const prediction = `${row?.prediction || 'Unknown'}`;
                const risk = `${row?.risk || 'Unknown'}`;
                const confidence = typeof row?.confidence === 'number' ? `${row.confidence}%` : typeof row?.confidence === 'string' ? `${row.confidence}%` : 'N/A';

                return (
                  <TableRow key={`${row?.timestamp || index}-${index}`} hover sx={{ '&:hover': { backgroundColor: 'rgba(37,99,235,0.06)' } }}>
                    <TableCell>{row?.meter_id || 'N/A'}</TableCell>
                    <TableCell><Chip label={prediction} color={prediction === 'Theft' ? 'error' : 'success'} size="small" /></TableCell>
                    <TableCell><Chip label={risk} color={risk === 'High' ? 'error' : risk === 'Medium' ? 'warning' : 'success'} size="small" /></TableCell>
                    <TableCell>{confidence}</TableCell>
                    <TableCell>{row?.timestamp || 'N/A'}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
        <TablePagination
          component="div"
          count={filteredHistory.length}
          page={page}
          onPageChange={(_, newPage) => setPage(newPage)}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={(event) => {
            setRowsPerPage(parseInt(event.target.value, 10));
            setPage(0);
          }}
          rowsPerPageOptions={[10, 25, 50]}
        />
      </CardContent>
    </Card>
  );
};

export default HistoryTable;
