import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import api, { getMe, loginRequest, logoutRequest, signupRequest } from '../services/api';

const TOKEN_KEY = 'energyguard.token';

const AuthContext = createContext(null);

/**
 * Session state for the whole application.
 *
 * The token lives in localStorage so a refresh does not sign the user out, and
 * is attached to every request by an axios interceptor registered here rather
 * than in each page.
 *
 * Worth being clear about in the write-up: a bearer token in localStorage is
 * readable by any script running on the page, and the app is served over plain
 * HTTP in development. This is a working authentication structure, not a
 * hardened one — put it behind HTTPS, and prefer an httpOnly cookie, before it
 * guards anything real.
 */
export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => {
    try {
      return localStorage.getItem(TOKEN_KEY) || '';
    } catch {
      return '';                       // private mode, or storage disabled
    }
  });
  const [loading, setLoading] = useState(true);

  const persistToken = useCallback((value) => {
    setToken(value || '');
    try {
      if (value) localStorage.setItem(TOKEN_KEY, value);
      else localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* storage unavailable — the session simply lasts until the tab closes */
    }
  }, []);

  // One interceptor for the whole app, so no page has to remember the header.
  useEffect(() => {
    const id = api.interceptors.request.use((config) => {
      if (token) config.headers.Authorization = `Bearer ${token}`;
      return config;
    });
    return () => api.interceptors.request.eject(id);
  }, [token]);

  // Resolve the stored token once on boot. An expired or revoked token simply
  // clears itself rather than leaving the UI in a half-signed-in state.
  useEffect(() => {
    let cancelled = false;
    if (!token) {
      setLoading(false);
      return undefined;
    }
    getMe(token)
      .then((response) => {
        if (!cancelled) setUser(response.data.user);
      })
      .catch(() => {
        if (!cancelled) {
          persistToken('');
          setUser(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [token, persistToken]);

  const login = useCallback(async (email, password, remember) => {
    const { data } = await loginRequest({ email, password, remember });
    persistToken(data.token);
    setUser(data.user);
    return data.user;
  }, [persistToken]);

  const signup = useCallback(async (fullName, email, password) => {
    const { data } = await signupRequest({ full_name: fullName, email, password });
    persistToken(data.token);
    setUser(data.user);
    return data.user;
  }, [persistToken]);

  const logout = useCallback(async () => {
    try {
      await logoutRequest();
    } catch {
      /* the server may already have expired the session; sign out locally anyway */
    }
    persistToken('');
    setUser(null);
  }, [persistToken]);

  const value = useMemo(
    () => ({ user, token, loading, login, signup, logout, isAuthenticated: Boolean(user) }),
    [user, token, loading, login, signup, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
};

export default AuthContext;
