import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Divider,
  Stack,
  Typography,
} from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFileRounded';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import DownloadIcon from '@mui/icons-material/DownloadRounded';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutlineRounded';
import ExpandMoreIcon from '@mui/icons-material/ExpandMoreRounded';
import {
  API_BASE,
  clearTransformerDataset,
  getTransformerDataset,
  uploadTransformerDataset,
} from '../services/api';
import { ink, line, status, statusFill, surface } from '../theme/tokens';

const REQUIRED_COLUMNS = [
  'transformer_id', 'reading_date', 'energy_supplied', 'energy_billed',
];
const OPTIONAL_COLUMNS = ['name', 'area', 'capacity_kva', 'meters', 'latitude', 'longitude'];

/**
 * Dataset control for Network Health.
 *
 * Two jobs. First, it says plainly where the numbers on this page come from —
 * an uploaded file, the seeder script, or nothing. That matters because the
 * seeded network is simulated, and a page that does not say so invites a
 * reviewer to mistake it for a live feed.
 *
 * Second, it lets the dataset be replaced from a CSV, so the network can be
 * changed without running Python.
 */
const TransformerDatasetPanel = ({ onDatasetChange }) => {
  const [dataset, setDataset] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [showFormat, setShowFormat] = useState(false);
  const fileInput = useRef(null);

  const refresh = useCallback(() => {
    getTransformerDataset()
      .then((response) => setDataset(response.data))
      .catch((err) => setError(err?.response?.data?.message || err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(refresh, [refresh]);

  const handleFile = async (event) => {
    const file = event.target.files?.[0];
    // Reset the input so choosing the same file twice still fires a change.
    event.target.value = '';
    if (!file) return;

    setUploading(true);
    setError('');
    setResult(null);
    try {
      const response = await uploadTransformerDataset(file);
      setResult(response.data);
      refresh();
      onDatasetChange?.();          // tell the page to reload its figures
    } catch (err) {
      setError(err?.response?.data?.message || err.message || 'Upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const handleClear = async () => {
    setUploading(true);
    setError('');
    setResult(null);
    try {
      await clearTransformerDataset();
      refresh();
      onDatasetChange?.();
    } catch (err) {
      setError(err?.response?.data?.message || err.message);
    } finally {
      setUploading(false);
    }
  };

  const source = dataset?.source;
  const sourceChip = {
    upload: { label: 'Uploaded dataset', colour: status.ok, fill: statusFill.ok },
    seed: { label: 'Simulated (seeded)', colour: status.warning, fill: statusFill.warning },
    none: { label: 'No dataset', colour: status.neutral, fill: statusFill.neutral },
  }[source] || { label: '—', colour: status.neutral, fill: statusFill.neutral };

  return (
    <Box
      sx={{
        border: `1px solid ${line.base}`,
        borderRadius: 4,
        backgroundColor: surface.card,
        p: { xs: 2, md: 2.5 },
      }}
    >
      <Stack
        direction={{ xs: 'column', md: 'row' }}
        spacing={2}
        justifyContent="space-between"
        alignItems={{ xs: 'flex-start', md: 'center' }}
      >
        <Stack direction="row" spacing={1.75} alignItems="center" sx={{ minWidth: 0 }}>
          <DescriptionOutlinedIcon sx={{ color: ink.secondary }} />
          <Box sx={{ minWidth: 0 }}>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
              <Typography variant="subtitle1">Network dataset</Typography>
              <Chip
                size="small"
                label={sourceChip.label}
                sx={{ color: sourceChip.colour, backgroundColor: sourceChip.fill, fontWeight: 600 }}
              />
            </Stack>

            {loading ? (
              <Typography variant="caption" sx={{ color: ink.muted }}>Checking…</Typography>
            ) : source === 'upload' ? (
              <Typography variant="caption" sx={{ color: ink.secondary, wordBreak: 'break-all' }}>
                {dataset.filename} · {dataset.transformers} transformers · {dataset.rows?.toLocaleString('en-IN')} rows
                {dataset.date_from ? ` · ${dataset.date_from} to ${dataset.date_to}` : ''}
                {dataset.uploaded_at ? ` · loaded ${dataset.uploaded_at}` : ''}
              </Typography>
            ) : source === 'seed' ? (
              <Typography variant="caption" sx={{ color: ink.secondary }}>
                {dataset.transformers} transformers generated by <code>seed_transformers.py</code>.
                These figures are <strong>simulated</strong> — upload a CSV to use real data.
              </Typography>
            ) : (
              <Typography variant="caption" sx={{ color: ink.secondary }}>
                No network data yet. Upload a transformer CSV to populate this page.
              </Typography>
            )}
          </Box>
        </Stack>

        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          <Button
            variant="contained"
            size="small"
            startIcon={uploading ? <CircularProgress size={14} color="inherit" /> : <UploadFileIcon />}
            disabled={uploading}
            onClick={() => fileInput.current?.click()}
          >
            {source === 'none' ? 'Upload dataset' : 'Replace dataset'}
          </Button>
          <Button
            size="small"
            variant="outlined"
            startIcon={<DownloadIcon />}
            component="a"
            href={`${API_BASE}/transformers/template`}
            download
          >
            Template
          </Button>
          {source === 'upload' && (
            <Button size="small" startIcon={<DeleteOutlineIcon />} onClick={handleClear} disabled={uploading}>
              Clear
            </Button>
          )}
          <input
            ref={fileInput}
            type="file"
            accept=".csv,text/csv"
            hidden
            onChange={handleFile}
            aria-label="Upload transformer dataset CSV"
          />
        </Stack>
      </Stack>

      {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}

      {result && (
        <Alert severity="success" sx={{ mt: 2 }}>
          Loaded <strong>{result.transformers}</strong> transformers and{' '}
          <strong>{result.rows?.toLocaleString('en-IN')}</strong> daily readings covering{' '}
          {result.days} days ({result.date_from} → {result.date_to}).
          {result.warnings?.length > 0 && (
            <Box component="ul" sx={{ m: 0, mt: 1, pl: 2.5 }}>
              {result.warnings.map((w, i) => (
                <li key={i}><Typography variant="caption">{w}</Typography></li>
              ))}
            </Box>
          )}
        </Alert>
      )}

      <Divider sx={{ my: 2 }} />

      <Button
        size="small"
        onClick={() => setShowFormat((v) => !v)}
        endIcon={
          <ExpandMoreIcon
            sx={{ transform: showFormat ? 'rotate(180deg)' : 'none', transition: 'transform .2s' }}
          />
        }
        aria-expanded={showFormat}
      >
        Expected CSV format
      </Button>

      <Collapse in={showFormat}>
        <Box sx={{ mt: 1.5 }}>
          <Typography variant="body2" sx={{ color: ink.secondary, mb: 1.5 }}>
            One row per transformer per day. Billed energy is taken at transformer level, which is
            the grain a utility billing export actually has — asking for a row per meter would make
            the file unusable.
          </Typography>

          <Stack direction="row" spacing={3} flexWrap="wrap" useFlexGap sx={{ mb: 1.5 }}>
            <Box>
              <Typography variant="overline" sx={{ color: ink.muted }}>Required</Typography>
              <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap sx={{ mt: 0.5 }}>
                {REQUIRED_COLUMNS.map((c) => (
                  <Chip key={c} size="small" label={c} sx={{ fontFamily: 'monospace', fontSize: 11 }} />
                ))}
              </Stack>
            </Box>
            <Box>
              <Typography variant="overline" sx={{ color: ink.muted }}>Optional</Typography>
              <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap sx={{ mt: 0.5 }}>
                {OPTIONAL_COLUMNS.map((c) => (
                  <Chip key={c} size="small" variant="outlined" label={c}
                        sx={{ fontFamily: 'monospace', fontSize: 11 }} />
                ))}
              </Stack>
            </Box>
          </Stack>

          <Box
            component="pre"
            sx={{
              m: 0, p: 1.5, overflowX: 'auto',
              backgroundColor: surface.sunken,
              border: `1px solid ${line.base}`,
              borderRadius: 2,
              fontSize: 11.5,
              fontFamily: 'monospace',
              color: ink.primary,
            }}
          >
{`transformer_id,name,area,capacity_kva,meters,reading_date,energy_supplied,energy_billed
DT-001,Sector 4 DT-1,Sector 4,250,88,2026-07-03,4821.40,4530.12
DT-001,Sector 4 DT-1,Sector 4,250,88,2026-07-04,4776.05,4498.88
DT-002,Old City DT-2,Old City,160,64,2026-07-03,3910.22,3115.90`}
          </Box>

          <Typography variant="caption" sx={{ color: ink.muted, display: 'block', mt: 1.5 }}>
            Dates accept YYYY-MM-DD, D/M/YYYY or M/D/YYYY. Common header spellings
            (<code>dt_id</code>, <code>supplied_kwh</code>, <code>zone</code>) are recognised.
            Uploading replaces the whole network — the file describes one network over one window,
            and merging two uploads would produce a network that never existed. Prediction history
            and meter records are never affected.
          </Typography>
        </Box>
      </Collapse>
    </Box>
  );
};

export default TransformerDatasetPanel;
