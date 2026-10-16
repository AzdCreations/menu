import { useState } from 'react';
import { Image, Linking, ScrollView, Text, View } from 'react-native';

import { api, errorMessage } from '@/api/client';
import type { Member, Photo, User, VenueHours, VenueStatus } from '@/api/types';
import { venueStatusLabel } from '@/i18n';
import { formatDateTime, WEEKDAYS } from '@/utils/format';
import { Badge, Button, Card, colors, Muted, notify, PromptModal, Row, Subtitle } from '../ui';

export type AdminVenue = {
  id: number;
  category: number;
  category_name: string;
  name: string;
  address: string;
  lat: string;
  lng: string;
  phone: string;
  status: VenueStatus;
  decision_reason: string;
  owner: User;
  photos: Photo[];
  hours: VenueHours[];
  members: Member[];
  possible_duplicate: { id: number; name: string; address: string; status: VenueStatus } | null;
  free_until: string | null;
  created_at: string;
};

const TONE: Record<VenueStatus, 'warning' | 'success' | 'danger' | 'neutral'> = {
  pending: 'warning',
  approved: 'success',
  rejected: 'danger',
  blocked: 'danger',
  closed: 'neutral',
};

/** Карточка заведения в админке с действиями модерации. */
export function AdminVenueCard({ venue, onChanged, expanded = false }: { venue: AdminVenue; onChanged: () => void; expanded?: boolean }) {
  const [open, setOpen] = useState(expanded);
  const [prompt, setPrompt] = useState<'reject' | 'block' | null>(null);
  const [busy, setBusy] = useState(false);

  async function act(action: string, reason = '') {
    setBusy(true);
    try {
      await api(`admin/venues/${venue.id}/${action}`, { method: 'POST', body: { reason } });
      onChanged();
    } catch (err) {
      notify(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <Row style={{ justifyContent: 'space-between' }}>
        <View style={{ flex: 1, gap: 2 }}>
          <Subtitle>{`#${venue.id} ${venue.name}`}</Subtitle>
          <Muted>{`${venue.category_name} · ${venue.address}`}</Muted>
          <Muted>{`Владелец: ${venue.owner.name || '—'} ${venue.owner.phone} · создано ${formatDateTime(venue.created_at)}`}</Muted>
        </View>
        <Badge label={venueStatusLabel('ru', venue.status)} tone={TONE[venue.status]} />
      </Row>
      {venue.possible_duplicate ? (
        <Badge label={`Возможный дубль: #${venue.possible_duplicate.id} ${venue.possible_duplicate.name}`} tone="danger" />
      ) : null}
      {venue.decision_reason ? <Muted>{`Причина: ${venue.decision_reason}`}</Muted> : null}

      {open ? (
        <View style={{ gap: 8 }}>
          {venue.photos.length ? (
            <ScrollView horizontal contentContainerStyle={{ gap: 8 }}>
              {venue.photos.map((photo) => (
                <Image key={photo.id} source={{ uri: photo.image }} style={{ width: 160, height: 110, borderRadius: 8 }} />
              ))}
            </ScrollView>
          ) : (
            <Muted>Фото нет</Muted>
          )}
          <Text style={{ color: colors.primary }} onPress={() => Linking.openURL(`https://maps.google.com/?q=${venue.lat},${venue.lng}`)}>
            {`Точка на карте: ${venue.lat}, ${venue.lng}`}
          </Text>
          <Muted>{`Телефон: ${venue.phone || '—'}`}</Muted>
          <Muted>
            {venue.hours
              .map((h) => `${WEEKDAYS.ru[h.weekday]} ${h.is_day_off ? 'вых.' : `${h.start?.slice(0, 5)}–${h.end?.slice(0, 5)}`}`)
              .join(' · ')}
          </Muted>
          <Muted>{`Сотрудники: ${venue.members.map((m) => `${m.name || m.phone} (${m.status})`).join(', ') || '—'}`}</Muted>
          {venue.free_until ? <Muted>{`Бесплатно до ${venue.free_until}`}</Muted> : null}
        </View>
      ) : null}

      <Row>
        <Button title={open ? 'Свернуть' : 'Подробнее'} small variant="ghost" onPress={() => setOpen(!open)} />
        {venue.status === 'pending' ? (
          <>
            <Button title="Одобрить" small onPress={() => act('approve')} loading={busy} />
            <Button title="Отклонить" small variant="danger" onPress={() => setPrompt('reject')} />
          </>
        ) : null}
        {venue.status === 'approved' ? <Button title="Заблокировать" small variant="danger" onPress={() => setPrompt('block')} /> : null}
        {venue.status === 'blocked' ? <Button title="Разблокировать" small variant="secondary" onPress={() => act('unblock')} loading={busy} /> : null}
      </Row>

      <PromptModal
        visible={prompt !== null}
        title={prompt === 'block' ? 'Причина блокировки' : 'Причина отклонения'}
        placeholder="Будет показана владельцу"
        submitLabel={prompt === 'block' ? 'Заблокировать' : 'Отклонить'}
        cancelLabel="Отмена"
        required
        onClose={() => setPrompt(null)}
        onSubmit={(reason) => {
          if (prompt) act(prompt, reason);
          setPrompt(null);
        }}
      />
    </Card>
  );
}
