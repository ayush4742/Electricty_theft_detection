import { useEffect, useState } from 'react';

const randomMeterId = () => Math.random().toString(16).slice(2, 10).toUpperCase();

const nowLabel = () =>
  new Date().toISOString().slice(0, 19).replace('T', ' ');

/**
 * Drives the whole dashboard from one synchronized "live feed".
 * Every `intervalMs`, a new simulated reading arrives, gets pushed into the
 * rolling history window, and totals/averages update to match — so the stat
 * cards, donut, bar chart, confidence trend, and "latest prediction" panel
 * all move together instead of each animating independently.
 */
export const useLiveDashboard = (initialData, { intervalMs = 3000, windowSize = 12 } = {}) => {
  const [state, setState] = useState(() => ({
    history: (initialData?.recent_history || []).slice(0, windowSize),
    totals: {
      total: initialData?.total_predictions ?? 0,
      theft: initialData?.theft_predictions ?? 0,
      normal: initialData?.normal_predictions ?? 0,
    },
    processingTime: 0.42,
  }));

  useEffect(() => {
    const id = setInterval(() => {
      setState((prev) => {
        const ratio = prev.totals.total ? prev.totals.theft / prev.totals.total : 0.16;
        const isTheft = Math.random() < Math.min(0.6, Math.max(0.05, ratio + (Math.random() - 0.5) * 0.12));

        const reading = {
          meter_id: randomMeterId(),
          prediction: isTheft ? 'Theft' : 'Normal',
          confidence: Math.round(55 + Math.random() * 44),
          timestamp: nowLabel(),
        };

        return {
          history: [reading, ...prev.history].slice(0, windowSize),
          totals: {
            total: prev.totals.total + 1,
            theft: prev.totals.theft + (isTheft ? 1 : 0),
            normal: prev.totals.normal + (isTheft ? 0 : 1),
          },
          processingTime: Math.round((0.3 + Math.random() * 0.4) * 100) / 100,
        };
      });
    }, intervalMs);

    return () => clearInterval(id);
  }, [intervalMs, windowSize]);

  const averageConfidence = state.history.length
    ? state.history.reduce((sum, item) => sum + (Number(item.confidence) || 0), 0) / state.history.length
    : 0;

  return {
    history: state.history,
    latestPrediction: state.history[0] || null,
    stats: {
      totalPredictions: state.totals.total,
      theftPredictions: state.totals.theft,
      normalPredictions: state.totals.normal,
      averageConfidence,
      processingTime: state.processingTime,
    },
  };
};

export default useLiveDashboard;