import { useState } from 'react';

import { api } from '@/api/client';
import type { Booking, BookingStatus, Paginated } from '@/api/types';
import { BookingCard } from '@/components/BookingCard';
import { Chip, Empty, ErrorBox, Loading, Muted, Row, Screen, Title } from '@/components/ui';
import { bookingStatusLabel } from '@/i18n';
import { useApi } from '@/utils/useApi';

const STATUSES: (BookingStatus | '')[] = ['', 'pending', 'confirmed', 'completed', 'no_show', 'cancelled_client', 'cancelled_specialist', 'rejected', 'expired'];

export default function AdminBookingsScreen() {
  const [status, setStatus] = useState<BookingStatus | ''>('');
  const { data, error, loading, reload } = useApi(() => api<Paginated<Booking>>('admin/bookings', { query: { status } }), [status]);
  return (
    <Screen>
      <Title>Записи</Title>
      <Row>
        {STATUSES.map((s) => (
          <Chip key={s || 'all'} label={s ? bookingStatusLabel('ru', s) : 'Все'} selected={s === status} onPress={() => setStatus(s)} />
        ))}
      </Row>
      {data ? <Muted>{`Всего: ${data.count} (показаны последние 50)`}</Muted> : null}
      {loading ? <Loading /> : null}
      {error ? <ErrorBox message={error} onRetry={reload} /> : null}
      {data?.results.length === 0 ? <Empty text="Записей нет" /> : null}
      {data?.results.map((booking) => (
        <BookingCard key={booking.id} booking={{ ...booking, specialist_name: `${booking.venue_name} · ${booking.specialist_name}` }} lang="ru" forSpecialist />
      ))}
    </Screen>
  );
}
