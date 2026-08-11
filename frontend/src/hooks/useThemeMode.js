import { useMemo, useState } from 'react';

export const useThemeMode = () => {
  const [mode, setMode] = useState('light');

  const themeMode = useMemo(
    () => ({
      mode,
      toggleMode: () => setMode((current) => (current === 'light' ? 'dark' : 'light')),
    }),
    [mode]
  );

  return themeMode;
};
