import * as ImagePicker from 'expo-image-picker';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Image, Platform, ScrollView, View } from 'react-native';

import { api, errorMessage } from '@/api/client';
import type { Member, Membership, OwnVenue } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { MembershipNotice, ProWelcome } from '@/components/ProWelcome';
import { Badge, Button, Card, confirmAction, ErrorBox, Field, Loading, Muted, notify, Row, Screen, Subtitle, Title } from '@/components/ui';
import { membershipStatusLabel, venueStatusLabel } from '@/i18n';
import { useApi } from '@/utils/useApi';
import { useMembership } from '@/utils/useMembership';

export default function VenueTab() {
  const { t } = useAuth();
  const membership = useMembership();
  if (membership.loading) return <Loading />;
  if (membership.error) return <Screen><ErrorBox message={membership.error} onRetry={membership.reload} retryLabel={t('retry')} /></Screen>;
  if (!membership.data) return <ProWelcome />;
  return <VenueManager membership={membership.data} />;
}

function VenueManager({ membership }: { membership: Membership }) {
  const { t, lang } = useAuth();
  const venueId = membership.venue.id;
  const venue = useApi(() => api<OwnVenue>(`pro/venues/${venueId}`), [venueId]);
  const members = useApi(
    () => (membership.is_owner ? api<Member[]>(`pro/venues/${venueId}/members`) : Promise.resolve([] as Member[])),
    [venueId, membership.is_owner],
  );
  const [form, setForm] = useState({ name: '', address: '', phone: '' });
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    if (venue.data) setForm({ name: venue.data.name, address: venue.data.address, phone: venue.data.phone });
  }, [venue.data]);

  async function run(key: string, action: () => Promise<unknown>) {
    setBusy(key);
    try {
      await action();
      venue.reload();
      members.reload();
    } catch (err) {
      notify(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  async function addPhoto() {
    const picked = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.7 });
    if (picked.canceled || !picked.assets[0]) return;
    const asset = picked.assets[0];
    const body = new FormData();
    if (Platform.OS === 'web') {
      const blob = await (await fetch(asset.uri)).blob();
      body.append('image', blob, asset.fileName ?? 'photo.jpg');
    } else {
      body.append('image', { uri: asset.uri, name: asset.fileName ?? 'photo.jpg', type: asset.mimeType ?? 'image/jpeg' } as any);
    }
    run('photo', () => api(`pro/venues/${venueId}/photos`, { method: 'POST', body }));
  }

  async function leave() {
    if (!(await confirmAction(`${t('leaveVenue')}?`, t('yes'), t('no')))) return;
    await run('leave', () => api('pro/membership/leave', { method: 'POST' }));
    router.replace('/pro');
  }

  if (venue.loading) return <Loading />;
  if (venue.error || !venue.data) return <Screen><ErrorBox message={venue.error ?? ''} onRetry={venue.reload} retryLabel={t('retry')} /></Screen>;
  const data = venue.data;
  const owner = data.is_owner;

  return (
    <Screen>
      <MembershipNotice membership={membership} />
      <Title>{data.name}</Title>
      <Badge label={venueStatusLabel(lang, data.status)} tone={data.status === 'approved' ? 'success' : data.status === 'pending' ? 'warning' : 'danger'} />
      {data.decision_reason ? <Muted>{data.decision_reason}</Muted> : null}

      <Card>
        <Subtitle>{t('photos')}</Subtitle>
        <ScrollView horizontal contentContainerStyle={{ gap: 8 }}>
          {data.photos.map((photo) => (
            <View key={photo.id} style={{ gap: 4 }}>
              <Image source={{ uri: photo.image }} style={{ width: 120, height: 90, borderRadius: 8 }} />
              {owner ? (
                <Button title={t('delete')} small variant="ghost" onPress={() => run(`p${photo.id}`, () => api(`pro/venues/${venueId}/photos/${photo.id}`, { method: 'DELETE' }))} />
              ) : null}
            </View>
          ))}
        </ScrollView>
        {owner ? <Button title={t('addPhoto')} variant="secondary" small onPress={addPhoto} loading={busy === 'photo'} /> : null}
      </Card>

      {owner ? (
        <Card>
          <Subtitle>{t('editVenue')}</Subtitle>
          <Field label={t('venueName')} value={form.name} onChangeText={(name) => setForm({ ...form, name })} />
          <Field label={t('address')} value={form.address} onChangeText={(address) => setForm({ ...form, address })} />
          <Field label={t('venuePhone')} value={form.phone} onChangeText={(phone) => setForm({ ...form, phone })} keyboardType="phone-pad" />
          {data.status === 'rejected' ? <Muted>{t('resubmitHint')}</Muted> : null}
          <Button title={t('save')} onPress={() => run('venue', () => api(`pro/venues/${venueId}`, { method: 'PATCH', body: form }))} loading={busy === 'venue'} />
        </Card>
      ) : (
        <Card>
          <Muted>{data.address}</Muted>
          <Muted>{data.phone}</Muted>
        </Card>
      )}

      {owner ? (
        <>
          <Subtitle>{t('members')}</Subtitle>
          {members.data?.map((member) => (
            <Card key={member.id}>
              <Row style={{ justifyContent: 'space-between' }}>
                <View style={{ flex: 1 }}>
                  <Subtitle>{member.name || member.phone}</Subtitle>
                  <Muted>{member.phone}</Muted>
                </View>
                <Badge label={member.is_owner ? '★' : membershipStatusLabel(lang, member.status)} tone={member.status === 'accepted' ? 'success' : member.status === 'pending' ? 'warning' : 'neutral'} />
              </Row>
              {member.status === 'pending' ? (
                <Row>
                  <Button title={t('approve')} small onPress={() => run(`m${member.id}`, () => api(`pro/members/${member.id}/approve`, { method: 'POST' }))} />
                  <Button title={t('reject')} small variant="danger" onPress={() => run(`m${member.id}`, () => api(`pro/members/${member.id}/reject`, { method: 'POST' }))} />
                </Row>
              ) : null}
              {member.status === 'accepted' && !member.is_owner ? (
                <Row>
                  <Button
                    title={t('remove')}
                    small
                    variant="danger"
                    onPress={async () => {
                      if (await confirmAction(`${t('remove')}: ${member.name}?`, t('yes'), t('no'))) {
                        run(`m${member.id}`, () => api(`pro/members/${member.id}/remove`, { method: 'POST' }));
                      }
                    }}
                  />
                  <Button
                    title={t('makeOwner')}
                    small
                    variant="secondary"
                    onPress={async () => {
                      if (await confirmAction(`${t('makeOwner')}: ${member.name}?`, t('yes'), t('no'))) {
                        run('owner', () => api(`pro/venues/${venueId}/transfer-owner`, { method: 'POST', body: { membership_id: member.id } }));
                      }
                    }}
                  />
                </Row>
              ) : null}
            </Card>
          ))}
        </>
      ) : (
        <Button title={t('leaveVenue')} variant="danger" onPress={leave} loading={busy === 'leave'} />
      )}
    </Screen>
  );
}
