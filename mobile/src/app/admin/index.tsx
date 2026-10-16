import { api } from '@/api/client';
import type { Paginated } from '@/api/types';
import { AdminVenueCard, type AdminVenue } from '@/components/admin/VenueCard';
import { Empty, ErrorBox, Loading, Muted, Screen, Title } from '@/components/ui';
import { useApi } from '@/utils/useApi';

/** Очередь модерации: новые заведения, старые заявки первыми. */
export default function ModerationScreen() {
  const { data, error, loading, reload } = useApi(() =>
    api<Paginated<AdminVenue>>('admin/venues', { query: { status: 'pending' } }),
  );
  return (
    <Screen>
      <Title>Модерация заведений</Title>
      <Muted>Заведение увидят клиенты только после одобрения. Проверьте фото, адрес, точку на карте и дубли.</Muted>
      {loading ? <Loading /> : null}
      {error ? <ErrorBox message={error} onRetry={reload} /> : null}
      {data?.results.length === 0 ? <Empty text="Очередь пуста" /> : null}
      {data?.results.map((venue) => (
        <AdminVenueCard key={venue.id} venue={venue} onChanged={reload} expanded />
      ))}
    </Screen>
  );
}
