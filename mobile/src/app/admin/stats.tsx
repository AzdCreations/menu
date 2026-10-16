import { useState } from 'react';
import { Text, View } from 'react-native';

import { api } from '@/api/client';
import type { BookingStatus, VenueStatus } from '@/api/types';
import { Card, Chip, colors, ErrorBox, Loading, Muted, Row, Screen, Subtitle, Title } from '@/components/ui';
import { bookingStatusLabel, venueStatusLabel } from '@/i18n';
import { useApi } from '@/utils/useApi';

type Stats = {
  period_days: number;
  venues: Partial<Record<VenueStatus, number>>;
  venues_by_category: { category__name_ru: string; venues: number }[];
  specialists: number;
  clients: number;
  new_users: number;
  bookings: Partial<Record<BookingStatus, number>>;
  bookings_total: number;
};

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <Card style={{ flex: 1, minWidth: 160 }}>
      <Muted>{label}</Muted>
      <Text style={{ fontSize: 28, fontWeight: '700', color: colors.text }}>{value}</Text>
    </Card>
  );
}

export default function AdminStatsScreen() {
  const [days, setDays] = useState(30);
  const { data, error, loading, reload } = useApi(() => api<Stats>('admin/stats', { query: { days } }), [days]);
  return (
    <Screen>
      <Title>Статистика</Title>
      <Row>
        {[7, 30, 90, 365].map((d) => (
          <Chip key={d} label={`${d} дн.`} selected={d === days} onPress={() => setDays(d)} />
        ))}
      </Row>
      {loading ? <Loading /> : null}
      {error ? <ErrorBox message={error} onRetry={reload} /> : null}
      {data ? (
        <>
          <Row>
            <Metric label="Одобренных заведений" value={data.venues.approved ?? 0} />
            <Metric label="На модерации" value={data.venues.pending ?? 0} />
            <Metric label="Специалистов" value={data.specialists} />
            <Metric label="Пользователей" value={data.clients} />
          </Row>
          <Row>
            <Metric label={`Новых пользователей за ${data.period_days} дн.`} value={data.new_users} />
            <Metric label={`Записей за ${data.period_days} дн.`} value={data.bookings_total} />
          </Row>
          <Card>
            <Subtitle>Записи по статусам</Subtitle>
            {Object.entries(data.bookings).map(([status, count]) => (
              <Row key={status} style={{ justifyContent: 'space-between' }}>
                <Text>{bookingStatusLabel('ru', status as BookingStatus)}</Text>
                <Text style={{ fontWeight: '600' }}>{count}</Text>
              </Row>
            ))}
            {Object.keys(data.bookings).length === 0 ? <Muted>Нет записей за период</Muted> : null}
          </Card>
          <Card>
            <Subtitle>Заведения</Subtitle>
            {Object.entries(data.venues).map(([status, count]) => (
              <Row key={status} style={{ justifyContent: 'space-between' }}>
                <Text>{venueStatusLabel('ru', status as VenueStatus)}</Text>
                <Text style={{ fontWeight: '600' }}>{count}</Text>
              </Row>
            ))}
            <View style={{ height: 8 }} />
            {data.venues_by_category.map((row) => (
              <Row key={row.category__name_ru} style={{ justifyContent: 'space-between' }}>
                <Muted>{row.category__name_ru}</Muted>
                <Muted>{String(row.venues)}</Muted>
              </Row>
            ))}
          </Card>
        </>
      ) : null}
    </Screen>
  );
}
