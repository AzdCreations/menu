import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { ScrollView, Text } from 'react-native';

import { api, ApiError, errorMessage } from '@/api/client';
import type { Booking, BookingField, VenueDetail } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { Button, Card, Chip, Empty, ErrorBox, Field, Loading, Muted, Notice, Row, Screen, Subtitle, Title, Toggle } from '@/components/ui';
import { formatDateTime, formatDay, formatDuration, isoTime, nextDays } from '@/utils/format';

const DAYS_AHEAD = 14;

export default function BookScreen() {
  const params = useLocalSearchParams<{
    membership: string;
    service: string;
    venue: string;
    specialistName?: string;
    serviceName?: string;
    duration?: string;
  }>();
  const { t, lang, status } = useAuth();
  const days = nextDays(DAYS_AHEAD);
  const [day, setDay] = useState(days[0]);
  const [slots, setSlots] = useState<string[] | null>(null);
  const [slot, setSlot] = useState<string | null>(null);
  const [fields, setFields] = useState<BookingField[]>([]);
  const [extra, setExtra] = useState<Record<string, unknown>>({});
  const [comment, setComment] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Booking | null>(null);

  useEffect(() => {
    api<VenueDetail>(`venues/${params.venue}`, { auth: false })
      .then((venue) => setFields(venue.booking_fields ?? []))
      .catch(() => setFields([]));
  }, [params.venue]);

  useEffect(() => {
    let active = true;
    setSlots(null);
    setSlot(null);
    api<{ slots: string[] }>(`specialists/${params.membership}/slots`, { auth: false, query: { service: params.service, date: day } })
      .then((data) => active && setSlots(data.slots))
      .catch((err) => active && (setSlots([]), setError(errorMessage(err))));
    return () => {
      active = false;
    };
  }, [day, params.membership, params.service]);

  async function submit() {
    if (status !== 'ready') return router.push('/login');
    setBusy(true);
    setError(null);
    try {
      const booking = await api<Booking>('bookings', {
        method: 'POST',
        body: { membership: Number(params.membership), service: Number(params.service), start: slot, comment, extra },
      });
      setResult(booking);
    } catch (err) {
      setError(errorMessage(err));
      if (err instanceof ApiError && (err.code === 'slot_taken' || err.code === 'slot_unavailable')) {
        // Время заняли — убираем его из списка окон.
        setSlots((current) => current?.filter((s) => s !== slot) ?? null);
        setSlot(null);
      }
    } finally {
      setBusy(false);
    }
  }

  if (result) {
    const confirmed = result.status === 'confirmed';
    return (
      <Screen>
        <Title>{confirmed ? t('bookedConfirmed') : t('requestSent')}</Title>
        <Card>
          <Subtitle>{result.venue_name}</Subtitle>
          <Muted>{`${result.specialist_name} · ${result.service_name}`}</Muted>
          <Text style={{ fontSize: 16, fontWeight: '600' }}>{formatDateTime(result.start, lang)}</Text>
        </Card>
        {!confirmed ? <Notice text={t('requestSentHint')} /> : null}
        <Button title={t('tabBookings')} onPress={() => router.replace('/client/bookings')} />
      </Screen>
    );
  }

  const requiredMissing = fields.some((f) => f.required && (extra[f.key] === undefined || extra[f.key] === ''));

  return (
    <Screen>
      <Card>
        <Subtitle>{params.serviceName}</Subtitle>
        <Muted>{`${params.specialistName ?? ''} · ${formatDuration(Number(params.duration ?? 0), lang)}`}</Muted>
      </Card>

      <Subtitle>{t('chooseDate')}</Subtitle>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
        {days.map((d) => (
          <Chip key={d} label={formatDay(d, lang)} selected={d === day} onPress={() => setDay(d)} />
        ))}
      </ScrollView>

      <Subtitle>{t('chooseTime')}</Subtitle>
      {slots === null ? <Loading /> : null}
      {slots?.length === 0 ? <Empty text={t('noSlots')} /> : null}
      <Row>
        {slots?.map((s) => (
          <Chip key={s} label={isoTime(s)} selected={s === slot} onPress={() => setSlot(s)} />
        ))}
      </Row>

      {fields.map((field) => {
        const label = (lang === 'uz' ? field.label_uz : field.label_ru) + (field.required ? ' *' : '');
        if (field.type === 'select') {
          return (
            <Card key={field.key}>
              <Muted>{label}</Muted>
              <Row>
                {(field.options ?? []).map((option) => (
                  <Chip key={option} label={option} selected={extra[field.key] === option} onPress={() => setExtra({ ...extra, [field.key]: option })} />
                ))}
              </Row>
            </Card>
          );
        }
        if (field.type === 'bool') {
          return <Toggle key={field.key} label={label} value={extra[field.key] === true} onChange={(v) => setExtra({ ...extra, [field.key]: v })} />;
        }
        return (
          <Field key={field.key} label={label} value={String(extra[field.key] ?? '')} onChangeText={(v) => setExtra({ ...extra, [field.key]: v })} />
        );
      })}

      <Field label={t('comment')} value={comment} onChangeText={setComment} multiline maxLength={500} />
      {error ? <ErrorBox message={error} /> : null}
      <Button title={t('sendRequest')} onPress={submit} loading={busy} disabled={!slot || requiredMissing} />
    </Screen>
  );
}
