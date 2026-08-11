import { Box, Typography } from '@mui/material';

const Footer = () => {
  return (
    <Box component="footer" sx={{ py: 3, textAlign: 'center', color: 'text.secondary', borderTop: '1px solid', borderColor: 'divider', mt: 3 }}>
      <Typography variant="body2">© 2026 AI-Based Electricity Theft Detection System</Typography>
      <Typography variant="body2">Developed by Ayush</Typography>
    </Box>
  );
};

export default Footer;
