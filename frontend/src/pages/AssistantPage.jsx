import { useEffect, useRef, useState } from 'react';
import {
  Alert,
  Avatar,
  Box,
  Chip,
  CircularProgress,
  IconButton,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import PersonIcon from '@mui/icons-material/Person';
import BuildIcon from '@mui/icons-material/Build';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import { askAgent, getAgentStatus, getAgentSuggestions } from '../services/api';

// Friendly names for the tools, so the "how I got this" chip reads like
// something a person would say rather than a function name.
const TOOL_LABEL = {
  network_overview: 'network overview',
  worst_transformers: 'worst transformers',
  transformer_detail: 'transformer detail',
  high_priority_meters: 'priority meters',
  meter_lookup: 'meter lookup',
  prediction_stats: 'model statistics',
  alert_summary: 'alert log',
  explain_concept: 'knowledge base',
};

const MessageBubble = ({ message }) => {
  const isUser = message.role === 'user';

  return (
    <Stack
      direction="row"
      spacing={1.5}
      sx={{ flexDirection: isUser ? 'row-reverse' : 'row', alignItems: 'flex-start' }}
    >
      <Avatar
        sx={{
          width: 32,
          height: 32,
          bgcolor: isUser ? 'secondary.main' : 'primary.main',
          mt: 0.5,
        }}
      >
        {isUser ? <PersonIcon fontSize="small" /> : <SmartToyIcon fontSize="small" />}
      </Avatar>

      <Box sx={{ maxWidth: '78%' }}>
        <Paper
          sx={{
            px: 2,
            py: 1.25,
            borderRadius: 3,
            borderTopRightRadius: isUser ? 4 : 12,
            borderTopLeftRadius: isUser ? 12 : 4,
            backgroundColor: isUser ? 'rgba(168,168,168,0.12)' : 'background.paper',
            borderColor: isUser ? 'rgba(168,168,168,0.3)' : undefined,
          }}
        >
          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.65 }}>
            {message.content}
          </Typography>
        </Paper>

        {/* Showing which tools ran is not decoration. It is how the user knows
            the answer came from the database and not from the model's
            imagination. */}
        {!isUser && message.tools?.length > 0 && (
          <Stack direction="row" spacing={0.75} sx={{ mt: 0.75, flexWrap: 'wrap', gap: 0.75 }}>
            <Tooltip title="This answer was read from the live database using these tools">
              <BuildIcon sx={{ fontSize: 14, color: 'text.secondary', mt: 0.4 }} />
            </Tooltip>
            {message.tools.map((tool, index) => (
              <Chip
                key={`${tool}-${index}`}
                size="small"
                label={TOOL_LABEL[tool] || tool}
                sx={{
                  height: 20,
                  fontSize: 11,
                  color: 'text.secondary',
                  backgroundColor: 'rgba(0,0,0,0.03)',
                }}
              />
            ))}
          </Stack>
        )}
      </Box>
    </Stack>
  );
};

const AssistantPage = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [error, setError] = useState('');
  const bottomRef = useRef(null);

  useEffect(() => {
    let timer;

    // The backend starts loading the local model the first time it is asked for
    // status, so keep checking until it reports ready. That turns a silent
    // 60-second wait into a visible "loading" chip.
    const check = () => {
      getAgentStatus()
        .then((response) => {
          setStatus(response.data);
          if (response.data.provider === 'ollama' && !response.data.model_ready) {
            timer = setTimeout(check, 4000);
          }
        })
        .catch((err) => setError(err?.response?.data?.message || err.message));
    };

    check();
    getAgentSuggestions()
      .then((response) => setSuggestions(response.data.suggestions || []))
      .catch(() => setSuggestions([]));

    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, busy]);

  const send = async (text) => {
    const question = (text ?? input).trim();
    if (!question || busy) return;

    const history = messages.map((message) => ({
      role: message.role,
      content: message.content,
    }));

    setMessages((previous) => [...previous, { role: 'user', content: question }]);
    setInput('');
    setBusy(true);
    setError('');

    try {
      const response = await askAgent(question, history);
      const data = response.data;
      setMessages((previous) => [
        ...previous,
        {
          role: 'assistant',
          content: data.answer,
          tools: (data.tools_used || []).map((call) => call.tool),
          provider: data.provider,
        },
      ]);
      if (data.provider && status && data.provider !== status.provider) {
        setStatus((previous) => ({ ...previous, provider: data.provider }));
      }
    } catch (err) {
      // Distinguish the three failures that actually happen, because "could
      // not reach the backend" sent people hunting for a dead server when the
      // real problem was a local model still grinding through the prompt.
      let reason;
      if (err?.code === 'ECONNABORTED' || /timeout/i.test(err?.message || '')) {
        reason =
          'That took too long to come back. A local model on CPU can need a few minutes for its ' +
          'first answer — try again now that it is loaded, or switch AI_PROVIDER to rules in ' +
          'backend/.env for instant answers.';
      } else if (err?.response) {
        reason = `The backend returned an error: ${
          err.response.data?.message || err.response.status
        }`;
      } else {
        reason =
          'I could not reach the backend. Check that Flask is running on port 5000 and that the ' +
          'API base URL in src/services/api.js points at it.';
      }
      setError(reason);
      setMessages((previous) => [...previous, { role: 'assistant', content: reason, tools: [] }]);
    } finally {
      setBusy(false);
    }
  };

  const providerChip = () => {
    if (!status) return null;
    if (status.provider === 'ollama') {
      return (
        <Chip
          size="small"
          color={status.model_ready ? 'success' : 'warning'}
          variant="outlined"
          icon={status.model_ready ? undefined : <CircularProgress size={11} sx={{ ml: 1 }} />}
          label={
            status.model_ready ? `Local model · ${status.model}` : `Loading ${status.model}…`
          }
        />
      );
    }
    if (status.provider === 'rules') {
      return <Chip size="small" color="warning" variant="outlined" label="Rules engine" />;
    }
    return <Chip size="small" variant="outlined" label={status.provider} />;
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 160px)' }}>
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="flex-start"
        sx={{ mb: 2 }}
      >
        <Box>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Typography variant="h4">Assistant</Typography>
            {providerChip()}
          </Stack>
          <Typography variant="body2" color="text.secondary">
            Ask about the network, a transformer, a meter, or how any of this works. Every number
            comes from a live database query.
          </Typography>
        </Box>
        {messages.length > 0 && (
          <Tooltip title="Clear conversation">
            <IconButton onClick={() => setMessages([])}>
              <RestartAltIcon />
            </IconButton>
          </Tooltip>
        )}
      </Stack>

      {status?.provider === 'rules' && (
        <Alert severity="info" sx={{ mb: 2 }}>
          {status.message}
        </Alert>
      )}
      {status?.enabled === false && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {status.message}
        </Alert>
      )}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Paper
        sx={{
          flexGrow: 1,
          overflowY: 'auto',
          p: 2.5,
          mb: 2,
          borderRadius: 3,
          backgroundColor: 'rgba(255,255,255,0.02)',
        }}
      >
        {messages.length === 0 ? (
          <Stack spacing={2} sx={{ py: 3 }}>
            <Stack alignItems="center" spacing={1}>
              <Avatar sx={{ bgcolor: 'primary.main', width: 48, height: 48 }}>
                <SmartToyIcon />
              </Avatar>
              <Typography variant="h6">What would you like to know?</Typography>
              <Typography variant="body2" color="text.secondary" textAlign="center">
                I can read the transformer balances, the model&apos;s predictions and the alert log.
              </Typography>
            </Stack>
            <Stack
              direction="row"
              spacing={1}
              sx={{ flexWrap: 'wrap', gap: 1, justifyContent: 'center', pt: 1 }}
            >
              {suggestions.map((suggestion) => (
                <Chip
                  key={suggestion}
                  label={suggestion}
                  onClick={() => send(suggestion)}
                  clickable
                  sx={{ borderRadius: 3 }}
                  variant="outlined"
                />
              ))}
            </Stack>
          </Stack>
        ) : (
          <Stack spacing={2.5}>
            {messages.map((message, index) => (
              <MessageBubble key={index} message={message} />
            ))}
            {busy && (
              <Stack direction="row" spacing={1.5} alignItems="center">
                <Avatar sx={{ width: 32, height: 32, bgcolor: 'primary.main' }}>
                  <SmartToyIcon fontSize="small" />
                </Avatar>
                <Stack direction="row" spacing={1} alignItems="center">
                  <CircularProgress size={14} />
                  <Typography variant="caption" color="text.secondary">
                    {status?.provider === 'ollama' && !status?.model_ready
                      ? 'Loading the model and reading the database — the first answer is slow…'
                      : 'Reading the database…'}
                  </Typography>
                </Stack>
              </Stack>
            )}
          </Stack>
        )}
        <div ref={bottomRef} />
      </Paper>

      <Stack direction="row" spacing={1.5}>
        <TextField
          fullWidth
          size="small"
          placeholder="Which transformer has the highest loss?"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              send();
            }
          }}
          disabled={busy || status?.enabled === false}
          sx={{ '& .MuiOutlinedInput-root': { borderRadius: 3 } }}
        />
        <IconButton
          color="primary"
          onClick={() => send()}
          disabled={busy || !input.trim() || status?.enabled === false}
          sx={{
            backgroundImage: '#111111',
            color: '#fff',
            borderRadius: 3,
            px: 2,
            '&.Mui-disabled': { backgroundImage: 'none', backgroundColor: 'rgba(0,0,0,0.04)' },
          }}
        >
          <SendIcon />
        </IconButton>
      </Stack>
    </Box>
  );
};

export default AssistantPage;
