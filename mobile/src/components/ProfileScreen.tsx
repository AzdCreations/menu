import { router } from 'expo-router';
import { useState } from 'react';
import { Text } from 'react-native';

import { api, errorMessage } from '@/api/client';
import type { AppNotification, Language, Paginated, User } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { formatDateTime } from '@/utils/format';
import { useApi } from '@/utils/useApi';
import { Button, Card, Chip, colors, confirmAction, ErrorBox, Field, Muted, notify, Row, Screen, Subtitle } from './ui';

export function ProfileScreen() {
  const { user, setUser, t, lang, mode, setMode, logout } = useAuth();
  const [name, setName] = useState(user?.name ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const notifications = useApi(() => api<Paginated<AppNotification> & { unread: number }>('notifications'));

  if (!user) return null;

  async function patch(body: Partial<User>) {
    setBusy(true);
    setError(null);
    try {
      setUser(await api<User>('me', { method: 'PATCH', body }));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function switchMode() {
    if (mode === 'pro') {
      await setMode('client');
      return router.replace('/client');
    }
    if (!user!.is_specialist) setUser(await api<User>('me/specialist', { method: 'POST' }));
    await setMode('pro');
    router.replace('/pro');
  }

  async function deleteAccount() {
    if (!(await confirmAction(t('deleteAccountConfirm'), t('delete'), t('cancel')))) return;
    try {
      await api('me', { method: 'DELETE' });
      await logout();
      router.replace('/login');
    } catch (err) {
      notify(errorMessage(err));
    }
  }

  async function markRead() {
    await api('notifications/read', { method: 'POST', body: {} });
    notifications.reload();
  }

  return (
    <Screen>
      <Card>
        <Subtitle>{user.phone}</Subtitle>
        <Field label={t('name')} value={name} onChangeText={setName} />
        <Button title={t('save')} small onPress={() => patch({ name })} loading={busy} disabled={name.trim() === user.name} />
        <Muted>{t('language')}</Muted>
        <Row>
          {(['uz', 'ru'] as Language[]).map((code) => (
            <Chip key={code} label={code === 'uz' ? "O'zbekcha" : 'Русский'} selected={lang === code} onPress={() => patch({ language: code })} />
          ))}
        </Row>
      </Card>
      {error ? <ErrorBox message={error} /> : null}

      <Button
        title={mode === 'pro' ? t('switchToClient') : user.is_specialist ? t('switchToPro') : t('becomeSpecialist')}
        variant="secondary"
        onPress={switchMode}
      />

      <Card>
        <Row style={{ justifyContent: 'space-between' }}>
          <Subtitle>{`${t('notifications')}${notifications.data?.unread ? ` (${notifications.data.unread})` : ''}`}</Subtitle>
          {notifications.data?.unread ? <Button title="✓" small variant="ghost" onPress={markRead} /> : null}
        </Row>
        {notifications.data?.results.slice(0, 10).map((n) => (
          <Card key={n.id} style={{ backgroundColor: n.is_read ? colors.card : colors.primarySoft }}>
            <Text style={{ fontWeight: '600', color: colors.text }}>{n.title}</Text>
            <Muted>{n.body}</Muted>
            <Muted style={{ fontSize: 12 }}>{formatDateTime(n.created_at, lang)}</Muted>
          </Card>
        ))}
        {notifications.data?.results.length === 0 ? <Muted>{t('empty')}</Muted> : null}
      </Card>

      <Button title={t('logout')} variant="secondary" onPress={async () => { await logout(); router.replace('/login'); }} />
      <Button title={t('deleteAccount')} variant="danger" onPress={deleteAccount} />
    </Screen>
  );
}
