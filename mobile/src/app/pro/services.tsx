import { useEffect, useState } from 'react';
import { Text, View } from 'react-native';

import { api, errorMessage } from '@/api/client';
import type { Membership, ScheduleException, Service, WorkingHours } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { MembershipNotice, ProWelcome } from '@/components/ProWelcome';
import { Button, Card, colors, ErrorBox, Field, Loading, Muted, notify, Row, Screen, Subtitle, Toggle } from '@/components/ui';
import { formatDuration, formatPrice, WEEKDAYS } from '@/utils/format';
import { useApi } from '@/utils/useApi';
import { useMembership } from '@/utils/useMembership';

type DayRow = { enabled: boolean; start: string; end: string; breakStart: string; breakEnd: string };

function toRows(hours: WorkingHours[]): DayRow[] {
  return Array.from({ length: 7 }, (_, weekday) => {
    const h = hours.find((item) => item.weekday === weekday);
    return {
      enabled: !!h,
      start: h?.start.slice(0, 5) ?? '10:00',
      end: h?.end.slice(0, 5) ?? '19:00',
      breakStart: h?.breaks[0]?.start ?? '',
      breakEnd: h?.breaks[0]?.end ?? '',
    };
  });
}

export default function ServicesScreen() {
  const { t } = useAuth();
  const membership = useMembership();
  if (membership.loading) return <Loading />;
  if (membership.error) return <Screen><ErrorBox message={membership.error} onRetry={membership.reload} retryLabel={t('retry')} /></Screen>;
  if (!membership.data) return <ProWelcome />;
  return <ServicesEditor membership={membership.data} reload={membership.reload} />;
}

function ServicesEditor({ membership, reload }: { membership: Membership; reload: () => void }) {
  const { t, lang } = useAuth();
  const [name, setName] = useState('');
  const [duration, setDuration] = useState('60');
  const [price, setPrice] = useState('');
  const [rows, setRows] = useState<DayRow[]>(toRows(membership.working_hours));
  const [profile, setProfile] = useState({
    display_name: membership.display_name,
    bio: membership.bio,
    auto_confirm: membership.auto_confirm,
    slot_step_minutes: String(membership.slot_step_minutes),
    min_lead_minutes: String(membership.min_lead_minutes),
    horizon_days: String(membership.horizon_days),
    buffer_minutes: String(membership.buffer_minutes),
  });
  const [offFrom, setOffFrom] = useState('');
  const [offTo, setOffTo] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const exceptions = useApi(() => api<ScheduleException[]>('pro/exceptions'));

  useEffect(() => setRows(toRows(membership.working_hours)), [membership.working_hours]);

  async function run(key: string, action: () => Promise<unknown>, done?: string) {
    setBusy(key);
    try {
      await action();
      reload();
      if (done) notify(done);
    } catch (err) {
      notify(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  const addService = () =>
    run('service', async () => {
      await api('pro/services', {
        method: 'POST',
        body: { name, duration_minutes: Number(duration), price: price ? Number(price.replace(/\D/g, '')) : null },
      });
      setName('');
      setPrice('');
    });

  const saveHours = () =>
    run(
      'hours',
      () =>
        api('pro/working-hours', {
          method: 'PUT',
          body: rows
            .map((row, weekday) => ({ row, weekday }))
            .filter(({ row }) => row.enabled)
            .map(({ row, weekday }) => ({
              weekday,
              start: row.start,
              end: row.end,
              breaks: row.breakStart && row.breakEnd ? [{ start: row.breakStart, end: row.breakEnd }] : [],
            })),
        }),
      t('saved'),
    );

  const saveProfile = () =>
    run(
      'profile',
      () =>
        api('pro/membership', {
          method: 'PATCH',
          body: {
            display_name: profile.display_name,
            bio: profile.bio,
            auto_confirm: profile.auto_confirm,
            slot_step_minutes: Number(profile.slot_step_minutes),
            min_lead_minutes: Number(profile.min_lead_minutes),
            horizon_days: Number(profile.horizon_days),
            buffer_minutes: Number(profile.buffer_minutes),
          },
        }),
      t('saved'),
    );

  const addDayOff = () =>
    run('exception', async () => {
      await api('pro/exceptions', { method: 'POST', body: { date_from: offFrom, date_to: offTo || offFrom, kind: 'day_off' } });
      setOffFrom('');
      setOffTo('');
      exceptions.reload();
    });

  const updateRow = (index: number, patch: Partial<DayRow>) =>
    setRows((current) => current.map((row, i) => (i === index ? { ...row, ...patch } : row)));

  const activeServices = membership.services.filter((s: Service) => s.is_active);

  return (
    <Screen>
      <MembershipNotice membership={membership} />

      <Subtitle>{t('myServices')}</Subtitle>
      {activeServices.map((service) => (
        <Card key={service.id}>
          <Row style={{ justifyContent: 'space-between' }}>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text }}>{service.name}</Text>
              <Muted>{[formatDuration(service.duration_minutes, lang), formatPrice(service.price, service.price_from, lang)].filter(Boolean).join(' · ')}</Muted>
            </View>
            <Button title={t('delete')} small variant="danger" onPress={() => run(`del${service.id}`, () => api(`pro/services/${service.id}`, { method: 'DELETE' }))} />
          </Row>
        </Card>
      ))}
      <Card>
        <Field label={t('serviceName')} value={name} onChangeText={setName} />
        <Row>
          <View style={{ flex: 1 }}>
            <Field label={t('duration')} value={duration} onChangeText={setDuration} keyboardType="number-pad" />
          </View>
          <View style={{ flex: 1 }}>
            <Field label={t('price')} value={price} onChangeText={setPrice} keyboardType="number-pad" />
          </View>
        </Row>
        <Button title={t('addService')} onPress={addService} loading={busy === 'service'} disabled={!name.trim() || !Number(duration)} />
      </Card>

      <Subtitle>{t('schedule')}</Subtitle>
      <Card>
        {rows.map((row, index) => (
          <View key={index} style={{ gap: 6, paddingVertical: 6, borderBottomWidth: index < 6 ? 1 : 0, borderBottomColor: colors.border }}>
            <Toggle label={`${WEEKDAYS[lang][index]} · ${t('workingDay')}`} value={row.enabled} onChange={(enabled) => updateRow(index, { enabled })} />
            {row.enabled ? (
              <Row>
                <TimeInput value={row.start} onChange={(start) => updateRow(index, { start })} />
                <Text>–</Text>
                <TimeInput value={row.end} onChange={(end) => updateRow(index, { end })} />
                <Muted>{t('breakTime')}</Muted>
                <TimeInput value={row.breakStart} placeholder="13:00" onChange={(breakStart) => updateRow(index, { breakStart })} />
                <Text>–</Text>
                <TimeInput value={row.breakEnd} placeholder="14:00" onChange={(breakEnd) => updateRow(index, { breakEnd })} />
              </Row>
            ) : null}
          </View>
        ))}
        <Button title={t('save')} onPress={saveHours} loading={busy === 'hours'} />
      </Card>

      <Subtitle>{t('exceptions')}</Subtitle>
      <Card>
        {exceptions.data?.map((exc) => (
          <Row key={exc.id} style={{ justifyContent: 'space-between' }}>
            <Text>{exc.date_from === exc.date_to ? exc.date_from : `${exc.date_from} — ${exc.date_to}`}</Text>
            <Button
              title={t('delete')}
              small
              variant="ghost"
              onPress={() => run(`exc${exc.id}`, async () => { await api(`pro/exceptions/${exc.id}`, { method: 'DELETE' }); exceptions.reload(); })}
            />
          </Row>
        ))}
        <Row>
          <View style={{ flex: 1 }}>
            <Field label={t('dateFrom')} value={offFrom} onChangeText={setOffFrom} placeholder="2026-11-01" />
          </View>
          <View style={{ flex: 1 }}>
            <Field label={t('dateTo')} value={offTo} onChangeText={setOffTo} placeholder="2026-11-07" />
          </View>
        </Row>
        <Button title={t('addDayOff')} variant="secondary" onPress={addDayOff} loading={busy === 'exception'} disabled={!/^\d{4}-\d{2}-\d{2}$/.test(offFrom)} />
      </Card>

      <Subtitle>{t('bookingSettings')}</Subtitle>
      <Card>
        <Field label={t('publicName')} value={profile.display_name} onChangeText={(v) => setProfile({ ...profile, display_name: v })} />
        <Field label={t('bio')} value={profile.bio} onChangeText={(v) => setProfile({ ...profile, bio: v })} multiline />
        <Toggle label={t('autoConfirm')} value={profile.auto_confirm} onChange={(v) => setProfile({ ...profile, auto_confirm: v })} />
        <Row>
          <NumberField label={t('slotStep')} value={profile.slot_step_minutes} onChange={(v) => setProfile({ ...profile, slot_step_minutes: v })} />
          <NumberField label={t('buffer')} value={profile.buffer_minutes} onChange={(v) => setProfile({ ...profile, buffer_minutes: v })} />
        </Row>
        <Row>
          <NumberField label={t('minLead')} value={profile.min_lead_minutes} onChange={(v) => setProfile({ ...profile, min_lead_minutes: v })} />
          <NumberField label={t('horizon')} value={profile.horizon_days} onChange={(v) => setProfile({ ...profile, horizon_days: v })} />
        </Row>
        <Button title={t('save')} onPress={saveProfile} loading={busy === 'profile'} />
      </Card>
    </Screen>
  );
}

function TimeInput({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <Field
      value={value}
      onChangeText={onChange}
      placeholder={placeholder ?? '10:00'}
      maxLength={5}
      keyboardType="numbers-and-punctuation"
      style={{ width: 76, paddingVertical: 8, textAlign: 'center' }}
    />
  );
}

function NumberField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <View style={{ flex: 1, minWidth: 140 }}>
      <Field label={label} value={value} onChangeText={(v) => onChange(v.replace(/\D/g, ''))} keyboardType="number-pad" />
    </View>
  );
}
