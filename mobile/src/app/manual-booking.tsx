import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { ScrollView, View } from 'react-native';

import { api, errorMessage } from '@/api/client';
import type { Membership } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { Button, Chip, ErrorBox, Field, Loading, Muted, Row, Screen, Subtitle } from '@/components/ui';
import { formatDay, nextDays, tashkentIso } from '@/utils/format';
import { useApi } from '@/utils/useApi';

const TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/;

/** Ручная запись клиента (звонок, пришёл без записи) или блокировка времени. */
export default function ManualBookingScreen() {
  const params = useLocalSearchParams<{ mode?: 'manual' | 'block'; date?: string }>();
  const isBlock = params.mode === 'block';
  const { t, lang } = useAuth();
  const days = nextDays(30);
  const [date, setDate] = useState(params.date && days.includes(params.date) ? params.date : days[0]);
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [service, setService] = useState<number | null>(null);
  const [clientName, setClientName] = useState('');
  const [clientPhone, setClientPhone] = useState('');
  const [comment, setComment] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const membership = useApi(() => api<Membership>('pro/membership'));

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      if (isBlock) {
        await api('pro/blocks', { method: 'POST', body: { start: tashkentIso(date, start), end: tashkentIso(date, end), comment } });
      } else {
        await api('pro/bookings/manual', {
          method: 'POST',
          body: { start: tashkentIso(date, start), service, client_name: clientName, client_phone: clientPhone, comment },
        });
      }
      router.back();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (membership.loading) return <Loading />;
  const services = membership.data?.services.filter((s) => s.is_active) ?? [];
  const valid = TIME_RE.test(start) && (isBlock ? TIME_RE.test(end) && end > start : service !== null);

  return (
    <Screen>
      <Stack.Screen options={{ title: isBlock ? t('blockTime') : t('addManual') }} />
      <Subtitle>{t('date')}</Subtitle>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
        {days.map((d) => (
          <Chip key={d} label={formatDay(d, lang)} selected={d === date} onPress={() => setDate(d)} />
        ))}
      </ScrollView>
      <Row>
        <View style={{ flex: 1 }}>
          <Field label={t('start')} value={start} onChangeText={setStart} placeholder="10:00" maxLength={5} />
        </View>
        {isBlock ? (
          <View style={{ flex: 1 }}>
            <Field label={t('end')} value={end} onChangeText={setEnd} placeholder="11:00" maxLength={5} />
          </View>
        ) : null}
      </Row>
      {!isBlock ? (
        <>
          <Subtitle>{t('services')}</Subtitle>
          {services.length === 0 ? <Muted>{t('addService')}</Muted> : null}
          <Row>
            {services.map((s) => (
              <Chip key={s.id} label={`${s.name} · ${s.duration_minutes} ${t('minutesShort')}`} selected={s.id === service} onPress={() => setService(s.id)} />
            ))}
          </Row>
          <Field label={t('clientName')} value={clientName} onChangeText={setClientName} />
          <Field label={t('clientPhone')} value={clientPhone} onChangeText={setClientPhone} keyboardType="phone-pad" />
        </>
      ) : null}
      <Field label={t('comment')} value={comment} onChangeText={setComment} />
      {error ? <ErrorBox message={error} /> : null}
      <Button title={t('save')} onPress={submit} loading={busy} disabled={!valid} />
    </Screen>
  );
}
