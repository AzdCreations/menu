import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { Platform } from 'react-native';

import { api, getRefreshToken, loadTokens, saveTokens, setLanguage, setOnAuthLost } from '@/api/client';
import { storage } from '@/api/storage';
import type { AuthResponse, Language, User } from '@/api/types';
import { translate, type TKey } from '@/i18n';
import { registerForPush } from './push';

export type Mode = 'client' | 'pro';
type Status = 'loading' | 'guest' | 'ready';

type AuthState = {
  status: Status;
  user: User | null;
  mode: Mode;
  lang: Language;
  t: (key: TKey) => string;
  completeLogin: (auth: AuthResponse) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<User | null>;
  setUser: (user: User) => void;
  setMode: (mode: Mode) => Promise<void>;
  setGuestLanguage: (lang: Language) => void;
};

const MODE_KEY = 'app.mode';
const LANG_KEY = 'app.lang';

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<Status>('loading');
  const [user, setUserState] = useState<User | null>(null);
  const [mode, setModeState] = useState<Mode>('client');
  const [guestLang, setGuestLang] = useState<Language>('uz');

  const lang: Language = user?.language ?? guestLang;
  useEffect(() => setLanguage(lang), [lang]);

  const reset = useCallback(() => {
    setUserState(null);
    setStatus('guest');
  }, []);

  useEffect(() => {
    setOnAuthLost(reset);
    (async () => {
      const [savedMode, savedLang] = await Promise.all([storage.get(MODE_KEY), storage.get(LANG_KEY)]);
      if (savedMode === 'pro') setModeState('pro');
      if (savedLang === 'ru' || savedLang === 'uz') setGuestLang(savedLang);
      if (!(await loadTokens())) return reset();
      try {
        const me = await api<User>('me');
        setUserState(me);
        setStatus('ready');
        if (Platform.OS !== 'web') registerForPush().catch(() => undefined);
      } catch {
        reset();
      }
    })();
    return () => setOnAuthLost(null);
  }, [reset]);

  const completeLogin = useCallback(async (auth: AuthResponse) => {
    await saveTokens({ access: auth.access, refresh: auth.refresh });
    let user = auth.user;
    if (!user.pd_consent && user.language !== guestLang) {
      // Новый пользователь: сохраняем язык, выбранный на экране входа.
      user = await api<User>('me', { method: 'PATCH', body: { language: guestLang } }).catch(() => user);
    }
    setUserState(user);
    setStatus('ready');
    if (Platform.OS !== 'web') registerForPush().catch(() => undefined);
  }, [guestLang]);

  const logout = useCallback(async () => {
    try {
      await api('auth/logout', { method: 'POST', body: { refresh: getRefreshToken() } });
    } catch {
      // выходим локально, даже если сервер недоступен
    }
    await saveTokens(null);
    reset();
  }, [reset]);

  const refreshUser = useCallback(async () => {
    try {
      const me = await api<User>('me');
      setUserState(me);
      return me;
    } catch {
      return null;
    }
  }, []);

  const setMode = useCallback(async (next: Mode) => {
    setModeState(next);
    await storage.set(MODE_KEY, next);
  }, []);

  const setGuestLanguage = useCallback((next: Language) => {
    setGuestLang(next);
    storage.set(LANG_KEY, next);
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      status,
      user,
      mode,
      lang,
      t: (key: TKey) => translate(lang, key),
      completeLogin,
      logout,
      refreshUser,
      setUser: setUserState,
      setMode,
      setGuestLanguage,
    }),
    [status, user, mode, lang, completeLogin, logout, refreshUser, setMode, setGuestLanguage],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth вне AuthProvider');
  return ctx;
}
