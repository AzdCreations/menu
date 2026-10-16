import { Redirect, router } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { api, errorMessage } from '@/api/client';
import type { User } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { Button, Chip, ErrorBox, Field, Row, Screen, Title, Toggle } from '@/components/ui';

export default function OnboardingScreen() {
  const { user, setUser, t, status } = useAuth();
  const [name, setName] = useState(user?.name ?? '');
  const [language, setLanguage] = useState(user?.language ?? 'uz');
  const [consent, setConsent] = useState(user?.pd_consent ?? false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (status === 'guest') return <Redirect href="/login" />;

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const updated = await api<User>('me', { method: 'PATCH', body: { name, language, pd_consent: consent } });
      setUser(updated);
      router.replace('/');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen>
      <View style={{ height: 40 }} />
      <Title>{t('onboardingTitle')}</Title>
      <Field label={t('name')} value={name} onChangeText={setName} autoFocus />
      <Row>
        <Chip label="O'zbekcha" selected={language === 'uz'} onPress={() => setLanguage('uz')} />
        <Chip label="Русский" selected={language === 'ru'} onPress={() => setLanguage('ru')} />
      </Row>
      <Toggle label={t('consent')} value={consent} onChange={setConsent} />
      {error ? <ErrorBox message={error} /> : null}
      <Button title={t('continue')} onPress={submit} loading={busy} disabled={!name.trim() || !consent} />
    </Screen>
  );
}
