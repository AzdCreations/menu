import { Text } from 'react-native';

import { api } from '@/api/client';
import type { Paginated } from '@/api/types';
import { Card, colors, Empty, ErrorBox, Loading, Muted, Screen, Title } from '@/components/ui';
import { formatDateTime } from '@/utils/format';
import { useApi } from '@/utils/useApi';

type Entry = {
  id: number;
  actor_phone: string;
  action: string;
  object_type: string;
  object_id: string;
  data: Record<string, unknown>;
  ip: string | null;
  created_at: string;
};

export default function AdminAuditScreen() {
  const { data, error, loading, reload } = useApi(() => api<Paginated<Entry>>('admin/audit-log'));
  return (
    <Screen>
      <Title>Журнал действий</Title>
      <Muted>Кто и что одобрил, заблокировал или изменил. Записи журнала нельзя изменить.</Muted>
      {loading ? <Loading /> : null}
      {error ? <ErrorBox message={error} onRetry={reload} /> : null}
      {data?.results.length === 0 ? <Empty text="Пока пусто" /> : null}
      {data?.results.map((entry) => (
        <Card key={entry.id}>
          <Text style={{ fontWeight: '600', color: colors.text }}>{`${entry.action} · ${entry.object_type} #${entry.object_id}`}</Text>
          <Muted>{`${formatDateTime(entry.created_at)} · ${entry.actor_phone || '—'} · ${entry.ip ?? ''}`}</Muted>
          {Object.keys(entry.data).length ? <Muted>{JSON.stringify(entry.data)}</Muted> : null}
        </Card>
      ))}
    </Screen>
  );
}
