import { Chip, Tooltip } from '@mui/material';
import SmsIcon from '@mui/icons-material/Sms';
import SmsFailedIcon from '@mui/icons-material/SmsFailed';
import RemoveCircleOutlineIcon from '@mui/icons-material/RemoveCircleOutline';

const SKIP_LABELS = {
  normal_prediction: 'Not required',
  cooldown: 'Cooldown',
  batch_limit: 'Summarised',
  alerts_disabled: 'Alerts off',
  below_min_confidence: 'Below threshold',
  summary_disabled: 'Summary off',
  alerting_skipped: 'Skipped',
};

const SKIP_HELP = {
  normal_prediction: 'This meter is Normal, so no SMS is sent.',
  cooldown: 'This meter was already alerted recently (ALERT_COOLDOWN_MINUTES).',
  batch_limit: 'Covered by the batch summary SMS instead of an individual message.',
  alerts_disabled: 'SMS alerting is turned off in the backend .env file.',
  below_min_confidence: 'Confidence was below ALERT_MIN_CONFIDENCE.',
  summary_disabled: 'Batch summary SMS is disabled.',
  alerting_skipped: 'Alerting was skipped for this row.',
};

/** One compact chip describing the SMS outcome for a single prediction row. */
const AlertStatusChip = ({ alertSent, alertError, alertSkipped, prediction }) => {
  if (alertSent) {
    return (
      <Tooltip title="SMS alert delivered to the configured number(s).">
        <Chip size="small" color="success" icon={<SmsIcon />} label="Sent" sx={{ fontWeight: 700 }} />
      </Tooltip>
    );
  }

  if (alertError) {
    return (
      <Tooltip title={alertError}>
        <Chip size="small" color="error" icon={<SmsFailedIcon />} label="Failed" sx={{ fontWeight: 700 }} />
      </Tooltip>
    );
  }

  const key = alertSkipped || (prediction === 'Theft' ? 'alerting_skipped' : 'normal_prediction');

  return (
    <Tooltip title={SKIP_HELP[key] || 'No SMS was sent for this row.'}>
      <Chip
        size="small"
        variant="outlined"
        icon={<RemoveCircleOutlineIcon />}
        label={SKIP_LABELS[key] || 'Not sent'}
      />
    </Tooltip>
  );
};

export default AlertStatusChip;
