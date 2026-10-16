import { useState } from 'react';

import { api } from '@/api/client';
import type { Paginated, VenueStatus } from '@/api/types';
import { AdminVenueCard, type AdminVenue } from '@/components/admin/VenueCard';
import { Chip, Empty, ErrorBox, Field, Loading, Muted, Row, Screen, Title } from '@/components/ui';
import { venueStatusLabel } from '@/i18n';
import { useApi } from '@/utils/useApi';

const STATUSES: (VenueStatus | '')[] = ['', 'pending', 'approved', 'rejected', 'blocked'];

export default function AdminVenuesScreen() {
  const [status, setStatus] = useState<VenueStatus | ''>('');
  const [query, setQuery] = useState('');
  const { data, error, loading, reload } = useApi(
    () => api<Paginated<AdminVenue>>('admin/venues', { query: { status, q: query.trim() } }),
    [status, query],
  );
  return (
    <Screen>
      <Title>Заведения</Title>
      <Field value={query} onChangeText={setQuery} placeholder="Название, адрес или телефон владельца" onSubmitEditing={reload} />
      <Row>
        {STATUSES.map((s) => (
          <Chip key={s || 'all'} label={s ? venueStatusLabel('ru', s) : 'Все'} selected={s === status} onPress={() => setStatus(s)} />
        ))}
      </Row>
      {data ? <Muted>{`Найдено: ${data.count}`}</Muted> : null}
      {loading ? <Loading /> : null}
      {error ? <ErrorBox message={error} onRetry={reload} /> : null}
      {data?.results.length === 0 ? <Empty text="Ничего не найдено" /> : null}
      {data?.results.map((venue) => (
        <AdminVenueCard key={venue.id} venue={venue} onChanged={reload} />
      ))}
    </Screen>
  );
}
