import { AppBar, Box, IconButton, Toolbar, Typography, useTheme } from '@mui/material';
import Brightness4Icon from '@mui/icons-material/Brightness4';
import Brightness7Icon from '@mui/icons-material/Brightness7';

const Navbar = ({ title, subtitle, onToggleMode, mode, sx }) => {
  const theme = useTheme();

  return (
    <AppBar
      position="sticky"
      elevation={0}
      sx={{
        borderBottom: `1px solid ${theme.palette.divider}`,
        background: mode === 'dark' ? 'linear-gradient(90deg, #07111f 0%, #10243d 100%)' : 'linear-gradient(90deg, #f8fbff 0%, #eef6ff 100%)',
        color: mode === 'dark' ? '#f8fbff' : '#0f172a',
        backdropFilter: 'blur(10px)',
        ...sx,
      }}
    >
      <Toolbar sx={{ justifyContent: 'space-between', px: { xs: 2, md: 3 }, py: { xs: 1, md: 1.2 } }}>
        <Box>
          <Typography variant="h6" fontWeight={800}>
            {title}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {subtitle}
          </Typography>
        </Box>
        <IconButton color="inherit" onClick={onToggleMode} sx={{ border: '1px solid', borderColor: 'divider' }}>
          {mode === 'dark' ? <Brightness7Icon /> : <Brightness4Icon />}
        </IconButton>
      </Toolbar>
    </AppBar>
  );
};

export default Navbar;
