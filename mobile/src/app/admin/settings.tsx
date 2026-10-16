import { useEffect, useState } from 'react';
import { View } from 'react-native';

import { api, errorMessage } from '@/api/client';
import { Button, Card, ErrorBox, Field, Loading, Muted, notify, Screen, Title, Toggle } from '@/components/ui';
import { useApi } from '@/utils/useApi';

type Settings = Record<string, number | boolean>;

const LABELS: Record<string, string> = {
  booking_response_minutes: 'Сколько минут специалист может ответить на заявку',
  client_cancel_min_hours: 'Клиент может отменить подтверждённую запись не позже чем за, ч',
  max_pending_per_client: 'Максимум заявок «Ожидает» у одного клиента',
  no_show_limit: 'Неявок за 90 дней до отключения автоподтверждения',
  max_venues_per_owner: 'Заведений на один аккаунт',
  payment_enabled: 'Оплата взноса включена (вне MVP)',
  entry_fee: 'Взнос за заведение, сум',
  free_period_months: 'Бесплатный период после одобрения, мес.',
  auto_complete_hours: 'Автоматически «Выполнена» через, ч после окончания',
};

export default function AdminSettingsScreen() {
  const { data, error, loading, reload } = useApi(() => api<Settings>('admin/settings'));
  const [draft, setDraft] = useState<Record<string, string | boolean>>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (data) setDraft(Object.fromEntries(Object.entries(data).map(([k, v]) => [k, typeof v === 'boolean' ? v : String(v)])));
  }, [data]);

  async function save() {
    setBusy(true);
    try {
      const body = Object.fromEntries(Object.entries(draft).map(([k, v]) => [k, typeof v === 'boolean' ? v : Number(v)]));
      await api('admin/settings', { method: 'PATCH', body });
      notify('Сохранено');
      reload();
    } catch (err) {
      notify(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen>
      <Title>Настройки</Title>
      <Muted>Изменения применяются сразу ко всем новым записям и пишутся в журнал.</Muted>
      {loading ? <Loading /> : null}
      {error ? <ErrorBox message={error} onRetry={reload} /> : null}
      <Card>
        {Object.entries(draft).map(([key, value]) => (
          <View key={key}>
            {typeof value === 'boolean' ? (
              <Toggle label={LABELS[key] ?? key} value={value} onChange={(v) => setDraft({ ...draft, [key]: v })} />
            ) : (
              <Field label={LABELS[key] ?? key} value={value} onChangeText={(v) => setDraft({ ...draft, [key]: v.replace(/\D/g, '') })} keyboardType="number-pad" />
            )}
          </View>
        ))}
        <Button title="Сохранить" onPress={save} loading={busy} />
      </Card>
    </Screen>
  );
}
