import { useState } from 'react';
import { View } from 'react-native';

import { api, errorMessage } from '@/api/client';
import type { Paginated, User } from '@/api/types';
import { Badge, Button, Card, Chip, Empty, ErrorBox, Field, Loading, Muted, notify, PromptModal, Row, Screen, Subtitle, Title } from '@/components/ui';
import { formatDateTime } from '@/utils/format';
import { useApi } from '@/utils/useApi';

type AdminUser = User & {
  block_reason: string;
  bookings_count: number;
  venues: { id: number; name: string; membership_status: string; is_owner: boolean }[];
};

const ROLES = [
  { value: '', label: 'Все' },
  { value: 'client', label: 'Клиенты' },
  { value: 'specialist', label: 'Специалисты' },
  { value: 'staff', label: 'Админы' },
];

export default function AdminUsersScreen() {
  const [role, setRole] = useState('');
  const [query, setQuery] = useState('');
  const [blocking, setBlocking] = useState<AdminUser | null>(null);
  const { data, error, loading, reload } = useApi(
    () => api<Paginated<AdminUser>>('admin/users', { query: { role, q: query.trim() } }),
    [role, query],
  );

  async function act(user: AdminUser, action: 'block' | 'unblock', reason = '') {
    try {
      await api(`admin/users/${user.id}/${action}`, { method: 'POST', body: { reason } });
      reload();
    } catch (err) {
      notify(errorMessage(err));
    }
  }

  return (
    <Screen>
      <Title>Пользователи</Title>
      <Field value={query} onChangeText={setQuery} placeholder="Телефон или имя" />
      <Row>
        {ROLES.map((r) => (
          <Chip key={r.value || 'all'} label={r.label} selected={r.value === role} onPress={() => setRole(r.value)} />
        ))}
      </Row>
      {data ? <Muted>{`Найдено: ${data.count}`}</Muted> : null}
      {loading ? <Loading /> : null}
      {error ? <ErrorBox message={error} onRetry={reload} /> : null}
      {data?.results.length === 0 ? <Empty text="Ничего не найдено" /> : null}
      {data?.results.map((user) => (
        <Card key={user.id}>
          <Row style={{ justifyContent: 'space-between' }}>
            <View style={{ flex: 1, gap: 2 }}>
              <Subtitle>{`${user.name || '—'} · ${user.phone}`}</Subtitle>
              <Muted>
                {[user.is_staff ? 'админ' : null, user.is_specialist ? 'специалист' : 'клиент', `записей: ${user.bookings_count}`, `с ${formatDateTime(user.created_at)}`]
                  .filter(Boolean)
                  .join(' · ')}
              </Muted>
              {user.venues.map((v) => (
                <Muted key={v.id}>{`${v.is_owner ? 'Владелец' : 'Сотрудник'}: ${v.name} (${v.membership_status})`}</Muted>
              ))}
              {user.block_reason ? <Muted>{`Причина блокировки: ${user.block_reason}`}</Muted> : null}
            </View>
            <Badge
              label={user.status === 'active' ? 'Активен' : user.status === 'blocked' ? 'Заблокирован' : 'Удалён'}
              tone={user.status === 'active' ? 'success' : 'danger'}
            />
          </Row>
          {!user.is_staff && user.status === 'active' ? (
            <Button title="Заблокировать" small variant="danger" onPress={() => setBlocking(user)} />
          ) : null}
          {user.status === 'blocked' ? <Button title="Разблокировать" small variant="secondary" onPress={() => act(user, 'unblock')} /> : null}
        </Card>
      ))}
      <PromptModal
        visible={blocking !== null}
        title={`Заблокировать ${blocking?.phone ?? ''}`}
        placeholder="Причина (увидит пользователь)"
        submitLabel="Заблокировать"
        cancelLabel="Отмена"
        required
        onClose={() => setBlocking(null)}
        onSubmit={(reason) => {
          if (blocking) act(blocking, 'block', reason);
          setBlocking(null);
        }}
      />
    </Screen>
  );
}
