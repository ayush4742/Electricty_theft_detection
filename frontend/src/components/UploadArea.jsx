import { Box, Button, Card, CardContent, CircularProgress, LinearProgress, Stack, Typography } from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import { motion } from 'framer-motion';
import { useDropzone } from 'react-dropzone';

const UploadArea = ({ onUpload, loading, acceptedFiles, setAcceptedFiles }) => {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { 'text/csv': ['.csv'] },
    multiple: false,
    onDrop: (files) => setAcceptedFiles(files),
  });

  return (
    <Card sx={{ borderRadius: 4, mb: 3, border: '1px solid', borderColor: 'divider', boxShadow: '0 18px 42px rgba(15,23,42,0.08)' }}>
      <CardContent>
        <Typography variant="h6" fontWeight={700} sx={{ mb: 2 }}>
          Upload CSV File
        </Typography>
        <motion.div whileHover={{ scale: 1.01 }} transition={{ duration: 0.2 }}>
          <Box
            {...getRootProps()}
            sx={{
              border: `2px dashed ${isDragActive ? '#2563eb' : '#cbd5e1'}`,
              borderRadius: 3,
              p: 4,
              textAlign: 'center',
              background: isDragActive ? 'linear-gradient(135deg, rgba(37,99,235,0.12) 0%, rgba(255,255,255,1) 100%)' : 'linear-gradient(135deg, #f8fbff 0%, #eef6ff 100%)',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
            }}
          >
            <input {...getInputProps()} />
            <CloudUploadIcon sx={{ fontSize: 54, color: 'primary.main', mb: 1.2 }} />
            <Typography variant="body1" fontWeight={600}>
              {isDragActive ? 'Drop the CSV here' : 'Drag and drop a CSV file, or click to browse'}
            </Typography>
            <Typography color="text.secondary" sx={{ mt: 0.8 }}>
              Supports SGCC-style datasets and large uploads.
            </Typography>
          </Box>
        </motion.div>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ mt: 2 }} alignItems={{ xs: 'stretch', sm: 'center' }}>
          <Button variant="contained" onClick={() => onUpload(acceptedFiles[0])} disabled={loading || !acceptedFiles.length} sx={{ minWidth: 220 }}>
            {loading ? <CircularProgress size={20} color="inherit" /> : 'Upload and Predict'}
          </Button>
          {acceptedFiles[0] && <Typography color="text.secondary">Selected: {acceptedFiles[0].name}</Typography>}
        </Stack>
        {loading && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Processing predictions...
            </Typography>
            <LinearProgress color="primary" />
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default UploadArea;
