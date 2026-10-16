import { router } from 'expo-router';
import { useState } from 'react';
import { RefreshControl } from 'react-native';

import { api, errorMessage } from '@/api/client';
import type { Booking, Paginated } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { BookingCard } from '@/components/BookingCard';
import { Button, Chip, confirmAction, Empty, ErrorBox, Loading, notify, Row, Screen } from '@/components/ui';
import { useApi } from '@/utils/useApi';

export default function MyBookingsScreen() {
  const { t, lang } = useAuth();
  const [scope, setScope] = useState<'upcoming' | 'past'>('upcoming');
  const { data, error, loading, refreshing, reload } = useApi(
    () => api<Paginated<Booking>>('bookings/my', { query: { scope } }),
    [scope],
  );

  async function cancel(booking: Booking) {
    if (!(await confirmAction(t('cancelConfirm'), t('yes'), t('no')))) return;
    try {
      await api(`bookings/${booking.id}/cancel`, { method: 'POST', body: {} });
      reload();
    } catch (err) {
      notify(errorMessage(err));
    }
  }

  return (
    <Screen refreshControl={<RefreshControl refreshing={refreshing} onRefresh={reload} />}>
      <Row>
        <Chip label={t('upcoming')} selected={scope === 'upcoming'} onPress={() => setScope('upcoming')} />
        <Chip label={t('past')} selected={scope === 'past'} onPress={() => setScope('past')} />
      </Row>
      {loading ? <Loading /> : null}
      {error ? <ErrorBox message={error} onRetry={reload} retryLabel={t('retry')} /> : null}
      {data?.results.length === 0 ? <Empty text={t('noBookings')} /> : null}
      {data?.results.map((booking) => (
        <BookingCard key={booking.id} booking={booking} lang={lang}>
          {['pending', 'confirmed'].includes(booking.status) && scope === 'upcoming' ? (
            <Button title={t('cancelBooking')} variant="danger" small onPress={() => cancel(booking)} />
          ) : null}
          {scope === 'past' || ['rejected', 'expired', 'cancelled_specialist'].includes(booking.status) ? (
            <Button
              title={t('bookAgain')}
              variant="secondary"
              small
              onPress={() => router.push({ pathname: '/venue/[id]', params: { id: booking.venue } })}
            />
          ) : null}
        </BookingCard>
      ))}
    </Screen>
  );
}
