import {
  AppBar,
  Avatar,
  Box,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Stack,
  Toolbar,
  Tooltip,
  Typography,
} from '@mui/material';
import DashboardIcon from '@mui/icons-material/GridViewRounded';
import UploadFileIcon from '@mui/icons-material/UploadFileRounded';
import HistoryIcon from '@mui/icons-material/HistoryRounded';
import ManageSearchIcon from '@mui/icons-material/ManageSearchRounded';
import ElectricalServicesIcon from '@mui/icons-material/ElectricBoltRounded';
import SmartToyIcon from '@mui/icons-material/SmartToyRounded';
import SmsIcon from '@mui/icons-material/NotificationsActiveRounded';
import MenuIcon from '@mui/icons-material/MenuRounded';
import LogoutIcon from '@mui/icons-material/LogoutRounded';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ink, line, radius, surface } from '../theme/tokens';

export const RAIL_WIDTH = 232;
export const RAIL_GAP = 16;

/**
 * Navigation. Seven destinations, each shown as icon + name.
 *
 * The rail used to be 72px and icon-only, which put the meaning of every
 * destination in a tooltip. That is tolerable for icons everyone recognises;
 * it is not tolerable for "Meter Lookup" versus "Network Health", which are
 * different pages with similar-looking glyphs. Labels are now always visible,
 * so nothing has to be hovered to be understood.
 *
 * Model Info was removed from the interface. The backend /model-info endpoint
 * is untouched and still serves.
 */
const links = [
  { label: 'Dashboard', path: '/dashboard', icon: <DashboardIcon /> },
  { label: 'CSV Upload', path: '/upload', icon: <UploadFileIcon /> },
  { label: 'Prediction History', path: '/history', icon: <HistoryIcon /> },
  { label: 'Meter Lookup', path: '/meters', icon: <ManageSearchIcon /> },
  { label: 'Network Health', path: '/network', icon: <ElectricalServicesIcon /> },
  { label: 'Assistant', path: '/assistant', icon: <SmartToyIcon /> },
  { label: 'SMS Alerts', path: '/alerts', icon: <SmsIcon /> },
];

/**
 * Wordmark. A transmission tower reduced to the "E" of EnergyGuard, drawn
 * inline so it costs no image request and inherits currentColor.
 */
const Wordmark = ({ size = 26, colour }) => (
  <Stack direction="row" spacing={0.25} alignItems="center" sx={{ color: colour || ink.onDark }}>
    <Box
      component="svg"
      role="img"
      aria-label="EnergyGuard"
      viewBox="0 0 24 24"
      sx={{ width: size, height: size }}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M13.5 2 5 13h6l-1.5 9L18 11h-6z" />
    </Box>
    <Box sx={{ width: 5, height: 5, borderRadius: '50%', backgroundColor: 'currentColor', mt: 1.2 }} />
  </Stack>
);

const initialsOf = (name = '') =>
  name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0] || '')
    .join('')
    .toUpperCase() || '?';

const itemSx = {
  borderRadius: radius.md,
  mb: 0.35,
  py: 1.05,
  px: 1.5,
  color: ink.onDarkMuted,
  '&:hover': { backgroundColor: surface.railHover, color: ink.onDark },
  // Active state is carried by a filled block AND full-strength white AND a
  // heavier label, so it is never signalled by colour alone.
  '&.active': {
    backgroundColor: surface.railHover,
    color: ink.onDark,
    '& .MuiListItemText-primary': { fontWeight: 700 },
  },
};

const Sidebar = ({ mobileOpen, onClose, onOpen }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const signOut = async () => {
    if (onClose) onClose();
    await logout();
    navigate('/login', { replace: true });
  };

  const navItems = (onNavigate) => (
    <List component="nav" aria-label="Main navigation" sx={{ px: 1, py: 0, width: '100%' }}>
      {links.map((item) => (
        <ListItemButton key={item.path} component={NavLink} to={item.path} onClick={onNavigate} sx={itemSx}>
          <ListItemIcon sx={{ minWidth: 38, color: 'inherit' }}>{item.icon}</ListItemIcon>
          <ListItemText primary={item.label} primaryTypographyProps={{ fontSize: '0.875rem' }} />
        </ListItemButton>
      ))}
    </List>
  );

  const account = (
    <Box sx={{ width: '100%', px: 1 }}>
      <Divider sx={{ borderColor: 'rgba(255,255,255,0.10)', mb: 1.25 }} />
      <Stack direction="row" spacing={1.25} alignItems="center" sx={{ px: 1.5, mb: 1 }}>
        <Avatar
          sx={{
            width: 30,
            height: 30,
            fontSize: '0.75rem',
            fontWeight: 700,
            backgroundColor: surface.railHover,
            color: ink.onDark,
          }}
        >
          {initialsOf(user?.full_name)}
        </Avatar>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="body2" noWrap sx={{ color: ink.onDark, fontWeight: 600 }}>
            {user?.full_name || 'Signed in'}
          </Typography>
          <Typography variant="caption" noWrap sx={{ color: ink.onDarkMuted, display: 'block' }}>
            {user?.email || ''}
          </Typography>
        </Box>
      </Stack>
      <ListItemButton onClick={signOut} sx={itemSx} aria-label="Sign out">
        <ListItemIcon sx={{ minWidth: 38, color: 'inherit' }}>
          <LogoutIcon />
        </ListItemIcon>
        <ListItemText primary="Sign out" primaryTypographyProps={{ fontSize: '0.875rem' }} />
      </ListItemButton>
    </Box>
  );

  const rail = (
    <Stack
      sx={{
        width: RAIL_WIDTH,
        backgroundColor: surface.rail,
        borderRadius: `${radius.xl}px`,
        py: 2.5,
        height: '100%',
        overflowY: 'auto',
      }}
    >
      <Stack direction="row" spacing={1} alignItems="center" sx={{ px: 2.5, mb: 2.5 }}>
        <Wordmark />
        <Typography variant="subtitle1" sx={{ fontWeight: 700, color: ink.onDark }}>
          EnergyGuard
        </Typography>
      </Stack>

      {navItems()}

      <Box sx={{ flexGrow: 1, minHeight: 16 }} />

      <Tooltip title="The console is connected to the EnergyGuard backend" placement="right" arrow>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ px: 2.5, mb: 1.5 }}>
          <Box sx={{ width: 7, height: 7, borderRadius: '50%', backgroundColor: '#4ade80' }} aria-hidden="true" />
          <Typography variant="caption" sx={{ color: ink.onDarkMuted, letterSpacing: '0.06em' }}>
            LIVE
          </Typography>
        </Stack>
      </Tooltip>

      {account}
    </Stack>
  );

  return (
    <>
      {/* Mobile top bar. Without this the navigation cannot be opened on a phone. */}
      <AppBar
        position="fixed"
        elevation={0}
        sx={{
          display: { xs: 'flex', md: 'none' },
          backgroundColor: surface.card,
          borderBottom: `1px solid ${line.base}`,
        }}
      >
        <Toolbar variant="dense" sx={{ gap: 1.25 }}>
          <IconButton edge="start" onClick={onOpen} aria-label="Open navigation menu" sx={{ color: ink.primary }}>
            <MenuIcon />
          </IconButton>
          <Wordmark size={20} colour={ink.primary} />
          <Typography variant="subtitle2" sx={{ fontWeight: 700, color: ink.primary }}>
            EnergyGuard
          </Typography>
        </Toolbar>
      </AppBar>
      <Toolbar variant="dense" sx={{ display: { xs: 'block', md: 'none' } }} />

      <Drawer
        variant="temporary"
        open={mobileOpen}
        onClose={onClose}
        ModalProps={{ keepMounted: true }}
        sx={{
          display: { xs: 'block', md: 'none' },
          '& .MuiDrawer-paper': { width: 264, backgroundColor: surface.rail, border: 'none', py: 1.5 },
        }}
      >
        <Stack direction="row" spacing={1} alignItems="center" sx={{ px: 2.5, py: 2 }}>
          <Wordmark size={22} />
          <Typography variant="subtitle1" sx={{ fontWeight: 700, color: ink.onDark }}>
            EnergyGuard
          </Typography>
        </Stack>
        <Stack sx={{ height: 'calc(100% - 76px)' }}>
          {navItems(onClose)}
          <Box sx={{ flexGrow: 1, minHeight: 16 }} />
          {account}
        </Stack>
      </Drawer>

      {/* Desktop: the rail floats clear of the window edge. */}
      <Box
        component="nav"
        sx={{
          display: { xs: 'none', md: 'block' },
          position: 'fixed',
          top: RAIL_GAP,
          left: RAIL_GAP,
          bottom: RAIL_GAP,
          width: RAIL_WIDTH,
          zIndex: (t) => t.zIndex.drawer,
        }}
      >
        {rail}
      </Box>
    </>
  );
};

export default Sidebar;
