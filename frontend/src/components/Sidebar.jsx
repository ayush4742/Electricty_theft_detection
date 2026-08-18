import { Drawer, List, ListItemButton, ListItemIcon, ListItemText, Toolbar, Typography, useTheme } from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import HistoryIcon from '@mui/icons-material/History';
import InfoIcon from '@mui/icons-material/Info';
import SmsIcon from '@mui/icons-material/Sms';
import { NavLink } from 'react-router-dom';

const drawerWidth = 240;

const links = [
  { label: 'Dashboard', path: '/', icon: <DashboardIcon /> },
  { label: 'CSV Upload', path: '/upload', icon: <UploadFileIcon /> },
  { label: 'Prediction History', path: '/history', icon: <HistoryIcon /> },
  { label: 'SMS Alerts', path: '/alerts', icon: <SmsIcon /> },
  { label: 'Model Info', path: '/model-info', icon: <InfoIcon /> },
];

const Sidebar = ({ mobileOpen, onClose, mode }) => {
  const theme = useTheme();
  const drawerContent = (
    <div>
      <Toolbar>
        <Typography variant="h6" fontWeight={700} color="primary">
          EnergyGuard
        </Typography>
      </Toolbar>
      <List>
        {links.map((item) => (
          <ListItemButton
            key={item.label}
            component={NavLink}
            to={item.path}
            onClick={onClose}
            sx={{
              mx: 1,
              borderRadius: 2,
              '&.active': {
                backgroundColor: theme.palette.primary.main,
                color: '#fff',
                '& .MuiListItemIcon-root': { color: '#fff' },
              },
            }}
          >
            <ListItemIcon>{item.icon}</ListItemIcon>
            <ListItemText primary={item.label} />
          </ListItemButton>
        ))}
      </List>
    </div>
  );

  return (
    <>
      <Drawer
        variant="temporary"
        open={mobileOpen}
        onClose={onClose}
        ModalProps={{ keepMounted: true }}
        sx={{
          display: { xs: 'block', md: 'none' },
          '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth, background: mode === 'dark' ? '#07111f' : '#f8fbff' },
        }}
      >
        {drawerContent}
      </Drawer>
      <Drawer
        variant="permanent"
        sx={{
          display: { xs: 'none', md: 'block' },
          '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth, background: mode === 'dark' ? '#07111f' : '#f8fbff' },
        }}
        open
      >
        {drawerContent}
      </Drawer>
    </>
  );
};

export default Sidebar;
