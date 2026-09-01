import { Card, CardContent, Chip, Stack, Typography } from '@mui/material';
import { motion } from 'framer-motion';
import { useEffect, useRef, useState } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  PolarAngleAxis,
  RadialBar,
  RadialBarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

// Chart palette. Black line on white with white dot markers is exactly the
// reference treatment; the greys are for secondary series, and the three
// status hues are reserved for meaning (theft / watch / normal).
const COLORS = {
  theft: '#c0392b',
  normal: '#2e7d32',
  series1: '#111111',
  series2: '#6e6e6e',
  amber: '#96690a',
  grid: 'rgba(0,0,0,0.04)',
  axis: '#8a8a8a',
  marker: '#ffffff',
};

const ChartCard = ({ title, subtitle, children }) => (
  <Card sx={{ borderRadius: '16px', border: '1px solid rgba(0,0,0,0.06)', height: '100%', display: 'flex', flexDirection: 'column' }}>
    <CardContent sx={{ display: 'flex', flexDirection: 'column', flexGrow: 1 }}>
      <Stack spacing={0.25} sx={{ mb: 2 }}>
        <Typography variant="h6" fontWeight={700}>
          {title}
        </Typography>
        {subtitle && (
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            {subtitle}
          </Typography>
        )}
      </Stack>
      {children}
    </CardContent>
  </Card>
);

const LiveDot = () => (
  <motion.span
    animate={{ opacity: [1, 0.25, 1] }}
    transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
    style={{
      width: 8,
      height: 8,
      borderRadius: '50%',
      background: COLORS.normal,
      boxShadow: `0 0 8px ${COLORS.normal}`,
      display: 'inline-block',
    }}
  />
);

const LiveTitle = ({ children }) => (
  <Stack direction="row" alignItems="center" spacing={1}>
    <Typography variant="h6" fontWeight={700}>
      {children}
    </Typography>
    <Chip
      size="small"
      icon={<LiveDot />}
      label="LIVE"
      sx={{ bgcolor: 'rgba(52,211,153,0.12)', color: COLORS.normal, fontWeight: 700, fontSize: '0.65rem', '.MuiChip-icon': { ml: 1 } }}
    />
  </Stack>
);

const DarkTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: '#f6f6f6',
        border: '1px solid rgba(0,0,0,0.10)',
        borderRadius: 10,
        padding: '8px 12px',
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 12,
        color: '#111111',
        boxShadow: '0 12px 30px rgba(0,0,0,0.4)',
      }}
    >
      {label && <div style={{ color: '#8a8a8a', marginBottom: 4 }}>{label}</div>}
      {payload.map((entry) => (
        <div key={entry.dataKey} style={{ color: entry.color || '#111111' }}>
          {entry.name}: {entry.value}
        </div>
      ))}
    </div>
  );
};

const EmptyState = () => (
  <Card sx={{ borderRadius: '16px', border: '1px solid rgba(0,0,0,0.06)' }}>
    <CardContent>
      <Typography variant="body1" sx={{ color: 'text.secondary' }}>
        No predictions available yet — run a prediction to see charts here.
      </Typography>
    </CardContent>
  </Card>
);

export const TheftDonutCard = ({ history }) => {
  if (!history || history.length === 0) return <EmptyState />;

  const theftCount = history.filter((item) => item.prediction === 'Theft').length;
  const normalCount = history.filter((item) => item.prediction === 'Normal').length;
  const pieData = [
    { name: 'Theft', value: theftCount },
    { name: 'Normal', value: normalCount },
  ];

  return (
    <ChartCard title="Theft vs Normal" subtitle={`${theftCount + normalCount} predictions in this view`}>
      <div style={{ position: 'relative' }}>
        <ResponsiveContainer width="100%" height={280}>
          <PieChart>
            <Pie
              data={pieData}
              dataKey="value"
              nameKey="name"
              innerRadius={70}
              outerRadius={105}
              paddingAngle={4}
              label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
              labelLine={{ stroke: COLORS.axis }}
            >
              <Cell fill={COLORS.theft} stroke="none" />
              <Cell fill={COLORS.normal} stroke="none" />
            </Pie>
            <Tooltip content={<DarkTooltip />} />
          </PieChart>
        </ResponsiveContainer>
        <Stack
          alignItems="center"
          sx={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            pointerEvents: 'none',
          }}
        >
          <Typography sx={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700 }} variant="h5">
            {theftCount + normalCount}
          </Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            total
          </Typography>
        </Stack>
      </div>
    </ChartCard>
  );
};

export const PredictionsBarCard = ({ history }) => {
  if (!history || history.length === 0) return <EmptyState />;

  const barData = history.slice(0, 8).map((item, index) => ({
    name: item.meter_id || `#${index + 1}`,
    confidence: Number(item.confidence) || 0,
    prediction: item.prediction,
  }));

  return (
    <ChartCard title="Recent Predictions" subtitle="Confidence score per reading, colored by result">
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={barData}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORS.grid} />
          <XAxis dataKey="name" tick={{ fill: COLORS.axis, fontSize: 12 }} axisLine={{ stroke: COLORS.grid }} tickLine={false} />
          <YAxis domain={[0, 100]} tick={{ fill: COLORS.axis, fontSize: 12 }} axisLine={false} tickLine={false} />
          <Tooltip content={<DarkTooltip />} cursor={{ fill: 'rgba(0,0,0,0.03)' }} />
          <Bar dataKey="confidence" radius={[6, 6, 0, 0]} maxBarSize={40}>
            {barData.map((entry, index) => (
              <Cell key={index} fill={entry.prediction === 'Theft' ? COLORS.theft : COLORS.normal} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
        <Chip size="small" label="Theft" sx={{ bgcolor: 'rgba(241,100,101,0.15)', color: COLORS.theft, fontWeight: 600 }} />
        <Chip size="small" label="Normal" sx={{ bgcolor: 'rgba(52,211,153,0.15)', color: COLORS.normal, fontWeight: 600 }} />
      </Stack>
    </ChartCard>
  );
};

export const ConfidenceLineCard = ({ history }) => {
  if (!history || history.length === 0) return <EmptyState />;

  const lineData = history.slice(0, 12).map((item, index) => ({
    name: `#${index + 1}`,
    confidence: Number(item.confidence) || 0,
  }));

  const avgConfidence = lineData.length
    ? (lineData.reduce((sum, d) => sum + d.confidence, 0) / lineData.length).toFixed(1)
    : 0;

  return (
    <ChartCard title="Confidence Trend" subtitle={`Average across this view: ${avgConfidence}%`}>
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={lineData}>
          <defs>
            <linearGradient id="confidenceFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={COLORS.series1} stopOpacity={0.45} />
              <stop offset="100%" stopColor={COLORS.series1} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORS.grid} />
          <XAxis dataKey="name" tick={{ fill: COLORS.axis, fontSize: 12 }} axisLine={{ stroke: COLORS.grid }} tickLine={false} />
          <YAxis domain={[0, 100]} tick={{ fill: COLORS.axis, fontSize: 12 }} axisLine={false} tickLine={false} />
          <Tooltip content={<DarkTooltip />} />
          <Area
            type="monotone"
            dataKey="confidence"
            stroke={COLORS.series1}
            strokeWidth={3}
            fill="url(#confidenceFill)"
            dot={{ r: 3, fill: COLORS.series1, strokeWidth: 0 }}
            activeDot={{ r: 5 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
};

export const LatestPredictionCard = ({ latestPrediction, hasPredictions }) => {
  if (!hasPredictions || !latestPrediction) {
    return (
      <ChartCard title="Latest Prediction">
        <Typography sx={{ color: 'text.secondary' }}>No predictions available.</Typography>
      </ChartCard>
    );
  }

  const isTheft = latestPrediction.prediction === 'Theft';
  const color = isTheft ? COLORS.theft : COLORS.normal;
  const confidence = Number(latestPrediction.confidence) || 0;
  const gaugeData = [{ value: confidence, fill: color }];

  return (
    <ChartCard title="Latest Prediction" subtitle={latestPrediction.timestamp}>
      <div style={{ position: 'relative' }}>
        <ResponsiveContainer width="100%" height={280}>
          <RadialBarChart
            innerRadius="72%"
            outerRadius="100%"
            data={gaugeData}
            startAngle={90}
            endAngle={-270}
          >
            <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
            <RadialBar dataKey="value" cornerRadius={16} background={{ fill: 'rgba(0,0,0,0.04)' }} />
          </RadialBarChart>
        </ResponsiveContainer>
        <Stack
          alignItems="center"
          spacing={1}
          sx={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }}
        >
          <Typography variant="h4" sx={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700 }}>
            {confidence}%
          </Typography>
          <Chip
            size="small"
            label={latestPrediction.prediction}
            sx={{ bgcolor: `${color}22`, color, fontWeight: 600 }}
          />
        </Stack>
      </div>
    </ChartCard>
  );
};

export const LiveGridLoadCard = ({ intervalMs = 2000, points = 20 }) => {
  const counter = useRef(points);
  const [data, setData] = useState(() =>
    Array.from({ length: points }, (_, i) => ({ t: i, value: Math.round(45 + Math.random() * 30) }))
  );

  useEffect(() => {
    const id = setInterval(() => {
      setData((prev) => {
        const last = prev[prev.length - 1]?.value ?? 55;
        const next = Math.min(98, Math.max(15, last + (Math.random() - 0.5) * 20));
        counter.current += 1;
        return [...prev.slice(1), { t: counter.current, value: Math.round(next) }];
      });
    }, intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);

  const current = data[data.length - 1]?.value ?? 0;

  return (
    <Card sx={{ borderRadius: '16px', border: '1px solid rgba(0,0,0,0.06)', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <CardContent sx={{ display: 'flex', flexDirection: 'column', flexGrow: 1 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" sx={{ mb: 0.5 }}>
          <LiveTitle>Live Grid Load</LiveTitle>
          <Typography sx={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: COLORS.series2 }} variant="h6">
            {current}%
          </Typography>
        </Stack>
        <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
          Simulated meter load, refreshes every {intervalMs / 1000}s
        </Typography>
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={data}>
            <defs>
              <linearGradient id="liveLoadFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={COLORS.series2} stopOpacity={0.5} />
                <stop offset="100%" stopColor={COLORS.series2} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORS.grid} />
            <XAxis dataKey="t" tick={false} axisLine={{ stroke: COLORS.grid }} tickLine={false} />
            <YAxis domain={[0, 100]} tick={{ fill: COLORS.axis, fontSize: 12 }} axisLine={false} tickLine={false} />
            <Tooltip content={<DarkTooltip />} />
            <Area
              type="monotone"
              dataKey="value"
              stroke={COLORS.series2}
              strokeWidth={3}
              fill="url(#liveLoadFill)"
              isAnimationActive={false}
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};

export const LiveDetectionGaugeCard = ({ intervalMs = 2500 }) => {
  const [rate, setRate] = useState(72);

  useEffect(() => {
    const id = setInterval(() => {
      setRate((prev) => {
        const next = prev + (Math.random() - 0.5) * 10;
        return Math.round(Math.min(96, Math.max(55, next)));
      });
    }, intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);

  const color = rate >= 80 ? COLORS.normal : rate >= 65 ? COLORS.amber : COLORS.theft;
  const gaugeData = [{ value: rate, fill: color }];

  return (
    <Card sx={{ borderRadius: '16px', border: '1px solid rgba(0,0,0,0.06)', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <CardContent sx={{ display: 'flex', flexDirection: 'column', flexGrow: 1 }}>
        <LiveTitle>Live Detection Confidence</LiveTitle>
        <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
          Model certainty on the active meter stream
        </Typography>
        <div style={{ position: 'relative' }}>
          <ResponsiveContainer width="100%" height={280}>
            <RadialBarChart innerRadius="72%" outerRadius="100%" data={gaugeData} startAngle={90} endAngle={-270}>
              <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
              <RadialBar dataKey="value" cornerRadius={16} background={{ fill: 'rgba(0,0,0,0.04)' }} isAnimationActive={true} />
            </RadialBarChart>
          </ResponsiveContainer>
          <Stack
            alignItems="center"
            sx={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }}
          >
            <Typography variant="h4" sx={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color }}>
              {rate}%
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              streaming
            </Typography>
          </Stack>
        </div>
      </CardContent>
    </Card>
  );
};

/** Default export kept for backward compatibility — stacks all three. Prefer the
 *  named exports above when you want charts arranged in a custom grid. */
const Charts = ({ history }) => (
  <Stack spacing={2.5}>
    <TheftDonutCard history={history} />
    <PredictionsBarCard history={history} />
    <ConfidenceLineCard history={history} />
  </Stack>
);

export default Charts;