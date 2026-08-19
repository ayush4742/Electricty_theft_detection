import { Alert, AlertTitle, Box, Chip, Stack, Typography } from '@mui/material';
import SmsIcon from '@mui/icons-material/Sms';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';

/**
 * Shows what happened with SMS alerting after a CSV upload.
 * It only renders counts returned by the backend - never any phone number.
 */
const AlertSummaryBanner = ({ summary }) => {
  if (!summary || !summary.theft_count) {
    return null;
  }

  const sent = Number(summary.alerts_sent || 0);
  const failed = Number(summary.alerts_failed || 0);
  const suppressed = Number(summary.alerts_suppressed || 0);
  const severity = failed > 0 ? 'warning' : sent > 0 ? 'error' : 'warning';

  return (
    <Alert severity={severity} icon={<WarningAmberIcon />} sx={{ borderRadius: 3 }}>
      <AlertTitle sx={{ fontWeight: 700 }}>
        🚨 Theft Detected — {summary.theft_count} meter{summary.theft_count === 1 ? '' : 's'}
      </AlertTitle>

      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: 1 }}>
        <Chip size="small" icon={<SmsIcon />} color="success" label={`SMS sent: ${sent}`} />
        {failed > 0 && <Chip size="small" color="error" label={`SMS failed: ${failed}`} />}
        {suppressed > 0 && <Chip size="small" color="default" label={`Not texted: ${suppressed}`} />}
        {summary.summary_sms_sent && <Chip size="small" color="info" label="Summary SMS sent" />}
      </Stack>

      {suppressed > 0 && (
        <Typography variant="body2" sx={{ mt: 1.5 }} color="text.secondary">
          Only the highest-confidence meters are texted individually (MAX_ALERTS_PER_BATCH), and a meter
          already alerted inside the cooldown window is skipped. Everything else is covered by the summary
          SMS and listed in the table below.
        </Typography>
      )}

      {failed > 0 && summary.alert_error && (
        <Box sx={{ mt: 1.5 }}>
          <Typography variant="body2" color="error.main">
            ⚠️ Theft detected, but SMS notification failed: {summary.alert_error}
          </Typography>
        </Box>
      )}
    </Alert>
  );
};

export default AlertSummaryBanner;
