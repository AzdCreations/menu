import { router } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { useEffect, useRef, useState } from 'react';
import { Linking, Platform, View } from 'react-native';

import { api, errorMessage } from '@/api/client';
import type { AuthResponse } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { Button, Card, Chip, ErrorBox, Field, Muted, Notice, Row, Screen, Title } from '@/components/ui';
import { normalizePhone } from '@/utils/format';

const DEV_LOGIN = process.env.EXPO_PUBLIC_DEV_LOGIN === '1';

type StartResponse = { token: string; bot_url: string; expires_at: string };
type StatusResponse = { status: 'pending' | 'confirmed' | 'used' | 'expired' } & Partial<AuthResponse>;

export default function LoginScreen() {
  const { t, lang, setGuestLanguage, completeLogin, status } = useAuth();
  const [login, setLogin] = useState<StartResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (status === 'ready') router.replace('/');
  }, [status]);

  useEffect(() => () => stopPolling(), []);

  function stopPolling() {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
  }

  async function openBot(url: string) {
    if (Platform.OS === 'web') {
      globalThis.open?.(url, '_blank');
      return;
    }
    // Ссылка t.me откроет приложение Telegram, если оно установлено.
    if (await Linking.canOpenURL(url)) await Linking.openURL(url);
    else await WebBrowser.openBrowserAsync(url);
  }

  async function startTelegram() {
    setError(null);
    setBusy(true);
    stopPolling();
    try {
      const started = await api<StartResponse>('auth/telegram/start', { method: 'POST', auth: false });
      setLogin(started);
      await openBot(started.bot_url);
      timer.current = setInterval(async () => {
        try {
          const result = await api<StatusResponse>(`auth/telegram/status/${started.token}`, { auth: false });
          if (result.status === 'confirmed' && result.access && result.refresh && result.user) {
            stopPolling();
            await completeLogin(result as AuthResponse);
            router.replace('/');
          } else if (result.status === 'expired' || result.status === 'used') {
            stopPolling();
            setLogin(null);
            setError(t('loginExpired'));
          }
        } catch {
          // временная ошибка сети — продолжаем опрос
        }
      }, 2000);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function devLogin() {
    setError(null);
    setBusy(true);
    try {
      const auth = await api<AuthResponse>('auth/dev-login', { method: 'POST', auth: false, body: { phone: normalizePhone(phone) } });
      await completeLogin(auth);
      router.replace('/');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function adminLogin() {
    setError(null);
    setBusy(true);
    try {
      const auth = await api<AuthResponse>('auth/admin-login', {
        method: 'POST',
        auth: false,
        body: { phone: normalizePhone(phone), password },
      });
      await completeLogin(auth);
      router.replace('/admin');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen>
      <View style={{ height: 40 }} />
      <Row style={{ justifyContent: 'flex-end' }}>
        <Chip label="O'zbekcha" selected={lang === 'uz'} onPress={() => setGuestLanguage('uz')} />
        <Chip label="Русский" selected={lang === 'ru'} onPress={() => setGuestLanguage('ru')} />
      </Row>
      <Title>{t('appName')}</Title>
      <Muted>{t('loginSubtitle')}</Muted>

      <Card>
        <Button title={t('loginTelegram')} onPress={startTelegram} loading={busy && !login} />
        <Muted>{t('loginTelegramHint')}</Muted>
        {login ? (
          <>
            <Notice text={t('loginWaiting')} />
            <Button title={t('loginOpenAgain')} variant="secondary" onPress={() => openBot(login.bot_url)} />
          </>
        ) : null}
      </Card>

      {error ? <ErrorBox message={error} /> : null}

      {DEV_LOGIN || Platform.OS === 'web' ? (
        <Card>
          <Muted>{Platform.OS === 'web' ? t('loginAdmin') : t('loginDev')}</Muted>
          <Field label={t('phone')} value={phone} onChangeText={setPhone} placeholder="+998 90 123 45 67" keyboardType="phone-pad" />
          {Platform.OS === 'web' ? (
            <>
              <Field label={t('password')} value={password} onChangeText={setPassword} secureTextEntry onSubmitEditing={adminLogin} />
              <Button title={t('signIn')} onPress={adminLogin} loading={busy} disabled={!phone || !password} />
            </>
          ) : null}
          {DEV_LOGIN ? (
            <Button title={t('loginDev')} variant="secondary" onPress={devLogin} loading={busy} disabled={!phone} />
          ) : null}
        </Card>
      ) : null}
    </Screen>
  );
}
