import { router, useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView } from 'react-native';

import { api, errorMessage } from '@/api/client';
import type { Booking } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { BookingCard } from '@/components/BookingCard';
import { MembershipNotice, ProWelcome } from '@/components/ProWelcome';
import { Button, Chip, confirmAction, Empty, ErrorBox, Loading, notify, PromptModal, Row, Screen, Subtitle, Toggle } from '@/components/ui';
import { addDays, formatDay, nextDays, todayTashkent } from '@/utils/format';
import { useMembership } from '@/utils/useMembership';

type Prompt = { booking: Booking; action: 'reject' | 'cancel' } | null;

export default function ScheduleScreen() {
  const { t, lang } = useAuth();
  const membership = useMembership();
  const days = nextDays(14);
  const [day, setDay] = useState(days[0]);
  const [allVenue, setAllVenue] = useState(false);
  const [dayBookings, setDayBookings] = useState<Booking[] | null>(null);
  const [requests, setRequests] = useState<Booking[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [prompt, setPrompt] = useState<Prompt>(null);

  const active = membership.data?.status === 'accepted';

  const load = useCallback(async () => {
    if (!active) return;
    const venueFlag = allVenue ? { venue: 1 } : {};
    try {
      const [list, pending] = await Promise.all([
        api<Booking[]>('pro/bookings', { query: { from: day, to: day, ...venueFlag } }),
        api<Booking[]>('pro/bookings', { query: { from: todayTashkent(), to: addDays(todayTashkent(), 60), status: 'pending', ...venueFlag } }),
      ]);
      setDayBookings(list);
      setRequests(pending);
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setRefreshing(false);
    }
  }, [active, day, allVenue]);

  useEffect(() => {
    setDayBookings(null);
    load();
  }, [load]);

  // Заявки живут 10 минут — обновляем список каждые 30 секунд, пока экран открыт.
  useFocusEffect(
    useCallback(() => {
      const timer = setInterval(load, 30000);
      return () => clearInterval(timer);
    }, [load]),
  );

  async function act(booking: Booking, action: string, reason = '') {
    try {
      await api(`bookings/${booking.id}/${action}`, { method: 'POST', body: { reason } });
      load();
    } catch (err) {
      notify(errorMessage(err));
      load();
    }
  }

  async function markVisit(booking: Booking, action: 'complete' | 'no-show') {
    if (action === 'no-show' && !(await confirmAction(`${t('noShow')}?`, t('yes'), t('no')))) return;
    act(booking, action);
  }

  if (membership.loading) return <Loading />;
  if (membership.error) return <Screen><ErrorBox message={membership.error} onRetry={membership.reload} retryLabel={t('retry')} /></Screen>;
  if (!membership.data) return <ProWelcome />;

  const started = (b: Booking) => new Date(b.start).getTime() <= Date.now();
  // Снятые блокировки времени не показываем.
  const visible = dayBookings?.filter((b) => b.kind === 'booking' || b.status === 'confirmed');

  return (
    <Screen refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}>
      <MembershipNotice membership={membership.data} />
      {active ? (
        <>
          {membership.data.is_owner ? <Toggle label={t('allSpecialists')} value={allVenue} onChange={setAllVenue} /> : null}
          {error ? <ErrorBox message={error} onRetry={load} retryLabel={t('retry')} /> : null}

          {requests.length ? <Subtitle>{`${t('requests')} (${requests.length})`}</Subtitle> : null}
          {requests.map((booking) => (
            <BookingCard key={booking.id} booking={booking} lang={lang} forSpecialist>
              <Row>
                <Button title={t('confirm')} small onPress={() => act(booking, 'confirm')} />
                <Button title={t('reject')} small variant="danger" onPress={() => setPrompt({ booking, action: 'reject' })} />
              </Row>
            </BookingCard>
          ))}

          <Row>
            <Button title={t('addManual')} small onPress={() => router.push({ pathname: '/manual-booking', params: { mode: 'manual', date: day } })} />
            <Button title={t('blockTime')} small variant="secondary" onPress={() => router.push({ pathname: '/manual-booking', params: { mode: 'block', date: day } })} />
          </Row>

          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
            {days.map((d) => (
              <Chip key={d} label={d === days[0] ? t('today') : formatDay(d, lang)} selected={d === day} onPress={() => setDay(d)} />
            ))}
          </ScrollView>

          {dayBookings === null ? <Loading /> : null}
          {visible?.length === 0 ? <Empty text={t('noRecords')} /> : null}
          {visible?.map((booking) => (
              <BookingCard key={booking.id} booking={booking} lang={lang} forSpecialist timeOnly>
                {booking.status === 'confirmed' ? (
                  <Row>
                    {booking.kind === 'booking' && started(booking) ? (
                      <>
                        <Button title={t('complete')} small onPress={() => markVisit(booking, 'complete')} />
                        <Button title={t('noShow')} small variant="secondary" onPress={() => markVisit(booking, 'no-show')} />
                      </>
                    ) : null}
                    {!started(booking) ? (
                      <Button
                        title={t('cancelByPro')}
                        small
                        variant="danger"
                        onPress={() =>
                          booking.kind === 'block' ? act(booking, 'cancel') : setPrompt({ booking, action: 'cancel' })
                        }
                      />
                    ) : null}
                  </Row>
                ) : null}
                {booking.status === 'pending' ? (
                  <Row>
                    <Button title={t('confirm')} small onPress={() => act(booking, 'confirm')} />
                    <Button title={t('reject')} small variant="danger" onPress={() => setPrompt({ booking, action: 'reject' })} />
                  </Row>
                ) : null}
              </BookingCard>
            ))}
        </>
      ) : null}

      <PromptModal
        visible={prompt !== null}
        title={prompt?.action === 'cancel' ? t('cancelReason') : t('reject')}
        placeholder={t('cancelReason')}
        submitLabel={prompt?.action === 'cancel' ? t('cancelByPro') : t('reject')}
        cancelLabel={t('close')}
        required={prompt?.action === 'cancel'}
        onClose={() => setPrompt(null)}
        onSubmit={(reason) => {
          if (prompt) act(prompt.booking, prompt.action, reason);
          setPrompt(null);
        }}
      />
    </Screen>
  );
}
