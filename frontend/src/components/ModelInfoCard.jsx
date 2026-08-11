import { Box, Card, CardContent, Chip, Stack, Typography } from '@mui/material';
import MemoryIcon from '@mui/icons-material/Memory';

const ModelInfoCard = ({ info }) => {
  return (
    <Card sx={{ borderRadius: 4, border: '1px solid', borderColor: 'divider', boxShadow: '0 18px 42px rgba(15,23,42,0.07)' }}>
      <CardContent>
        <Stack direction={{ xs: 'column', md: 'row' }} justifyContent="space-between" spacing={2} alignItems={{ xs: 'flex-start', md: 'center' }} sx={{ mb: 2 }}>
          <Box>
            <Typography variant="h6" fontWeight={700}>
              Model Information
            </Typography>
            <Typography color="text.secondary" sx={{ mt: 0.5 }}>
              A professional summary of the loaded AI model used for inference.
            </Typography>
          </Box>
          <Chip icon={<MemoryIcon />} label="Operational" color="primary" />
        </Stack>
        <Stack spacing={1.6}>
          <Typography><strong>Model Name:</strong> {info?.model || 'Loading...'}</Typography>
          <Typography><strong>Algorithm:</strong> Random Forest</Typography>
          <Typography><strong>Total Features:</strong> {info?.total_features || 'Loading...'}</Typography>
          <Typography><strong>Dataset:</strong> Electricity theft detection dataset</Typography>
          <Typography><strong>Status:</strong> {info?.status || 'Loading...'}</Typography>
          <Typography><strong>Last Updated:</strong> 2026-07-25</Typography>
        </Stack>
      </CardContent>
    </Card>
  );
};

export default ModelInfoCard;
