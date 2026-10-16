import { useState } from 'react';
import { View } from 'react-native';

import { api, errorMessage } from '@/api/client';
import type { Category } from '@/api/types';
import { Badge, Button, Card, ErrorBox, Field, Loading, Muted, notify, Row, Screen, Subtitle, Title, Toggle } from '@/components/ui';
import { useApi } from '@/utils/useApi';

type Draft = {
  name_ru: string;
  name_uz: string;
  specialist_name_ru: string;
  specialist_name_uz: string;
  icon: string;
  order: string;
  is_active: boolean;
  booking_fields: string;
};

const EMPTY: Draft = {
  name_ru: '',
  name_uz: '',
  specialist_name_ru: '',
  specialist_name_uz: '',
  icon: '',
  order: '0',
  is_active: true,
  booking_fields: '[]',
};

const FIELDS_HINT =
  'Доп. поля анкеты записи, JSON. Пример: [{"key":"reason","label_ru":"Причина визита","label_uz":"Tashrif sababi","type":"select","options":["Осмотр","Боль"],"required":true}]. Типы: text, select, bool.';

function toDraft(category: Category): Draft {
  return {
    name_ru: category.name_ru,
    name_uz: category.name_uz,
    specialist_name_ru: category.specialist_name_ru,
    specialist_name_uz: category.specialist_name_uz,
    icon: category.icon,
    order: String(category.order),
    is_active: category.is_active,
    booking_fields: JSON.stringify(category.booking_fields ?? [], null, 1),
  };
}

export default function AdminCategoriesScreen() {
  const { data, error, loading, reload } = useApi(() => api<Category[]>('admin/categories/'));
  const [editing, setEditing] = useState<number | 'new' | null>(null);

  return (
    <Screen>
      <Title>Направления</Title>
      <Muted>Виды бронирования. Скрытое направление не видно клиентам и специалистам.</Muted>
      {loading ? <Loading /> : null}
      {error ? <ErrorBox message={error} onRetry={reload} /> : null}
      {data?.map((category) =>
        editing === category.id ? (
          <CategoryForm key={category.id} id={category.id} initial={toDraft(category)} onDone={() => { setEditing(null); reload(); }} />
        ) : (
          <Card key={category.id}>
            <Row style={{ justifyContent: 'space-between' }}>
              <View style={{ flex: 1 }}>
                <Subtitle>{`${category.name_ru} / ${category.name_uz}`}</Subtitle>
                <Muted>{`Специалист: ${category.specialist_name_ru} / ${category.specialist_name_uz} · полей анкеты: ${category.booking_fields.length}`}</Muted>
              </View>
              <Badge label={category.is_active ? 'Активно' : 'Скрыто'} tone={category.is_active ? 'success' : 'neutral'} />
            </Row>
            <Button title="Изменить" small variant="secondary" onPress={() => setEditing(category.id)} />
          </Card>
        ),
      )}
      {editing === 'new' ? (
        <CategoryForm initial={EMPTY} onDone={() => { setEditing(null); reload(); }} />
      ) : (
        <Button title="Добавить направление" onPress={() => setEditing('new')} />
      )}
    </Screen>
  );
}

function CategoryForm({ id, initial, onDone }: { id?: number; initial: Draft; onDone: () => void }) {
  const [draft, setDraft] = useState<Draft>(initial);
  const [busy, setBusy] = useState(false);
  const set = (patch: Partial<Draft>) => setDraft({ ...draft, ...patch });

  async function save() {
    let fields: unknown;
    try {
      fields = JSON.parse(draft.booking_fields || '[]');
    } catch {
      return notify('Поля анкеты: неверный JSON');
    }
    setBusy(true);
    try {
      const body = { ...draft, order: Number(draft.order) || 0, booking_fields: fields };
      await api(id ? `admin/categories/${id}/` : 'admin/categories/', { method: id ? 'PATCH' : 'POST', body });
      onDone();
    } catch (err) {
      notify(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <Row>
        <View style={{ flex: 1, minWidth: 200 }}>
          <Field label="Название (рус)" value={draft.name_ru} onChangeText={(name_ru) => set({ name_ru })} />
        </View>
        <View style={{ flex: 1, minWidth: 200 }}>
          <Field label="Название (узб)" value={draft.name_uz} onChangeText={(name_uz) => set({ name_uz })} />
        </View>
      </Row>
      <Row>
        <View style={{ flex: 1, minWidth: 200 }}>
          <Field label="Специалист (рус): мастер, врач" value={draft.specialist_name_ru} onChangeText={(v) => set({ specialist_name_ru: v })} />
        </View>
        <View style={{ flex: 1, minWidth: 200 }}>
          <Field label="Специалист (узб): usta, shifokor" value={draft.specialist_name_uz} onChangeText={(v) => set({ specialist_name_uz: v })} />
        </View>
      </Row>
      <Row>
        <View style={{ flex: 1, minWidth: 160 }}>
          <Field label="Иконка" value={draft.icon} onChangeText={(icon) => set({ icon })} />
        </View>
        <View style={{ flex: 1, minWidth: 160 }}>
          <Field label="Порядок" value={draft.order} onChangeText={(order) => set({ order })} keyboardType="number-pad" />
        </View>
      </Row>
      <Toggle label="Активно" value={draft.is_active} onChange={(is_active) => set({ is_active })} />
      <Field label="Поля анкеты записи" value={draft.booking_fields} onChangeText={(booking_fields) => set({ booking_fields })} multiline />
      <Muted>{FIELDS_HINT}</Muted>
      <Row>
        <Button title="Сохранить" onPress={save} loading={busy} />
        <Button title="Отмена" variant="secondary" onPress={onDone} />
      </Row>
    </Card>
  );
}
