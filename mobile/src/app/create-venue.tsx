import * as Location from 'expo-location';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { View } from 'react-native';

import { api, errorMessage } from '@/api/client';
import type { Category, OwnVenue } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { Button, Card, Chip, ErrorBox, Field, Muted, notify, Row, Screen, Subtitle } from '@/components/ui';

// По умолчанию: понедельник–суббота 09:00–20:00, воскресенье выходной. Владелец поменяет позже.
const DEFAULT_HOURS = Array.from({ length: 7 }, (_, weekday) =>
  weekday === 6 ? { weekday, is_day_off: true } : { weekday, start: '09:00', end: '20:00', is_day_off: false },
);

export default function CreateVenueScreen() {
  const { t, setMode } = useAuth();
  const [categories, setCategories] = useState<Category[]>([]);
  const [form, setForm] = useState({ category: 0, name: '', address: '', phone: '', lat: '', lng: '' });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Category[]>('categories', { auth: false }).then((data) => {
      setCategories(data);
      if (data[0]) setForm((f) => ({ ...f, category: f.category || data[0].id }));
    });
  }, []);

  async function useLocation() {
    try {
      const permission = await Location.requestForegroundPermissionsAsync();
      if (!permission.granted) return;
      const position = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
      setForm((f) => ({ ...f, lat: position.coords.latitude.toFixed(6), lng: position.coords.longitude.toFixed(6) }));
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const venue = await api<OwnVenue>('pro/venues', { method: 'POST', body: { ...form, hours: DEFAULT_HOURS } });
      await setMode('pro');
      notify(venue.duplicates?.length ? `${t('venuePending')}\n\n${t('duplicatesFound')}` : t('venuePending'));
      router.replace('/pro/services');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const valid = form.category && form.name.trim() && form.address.trim() && form.lat && form.lng;

  return (
    <Screen>
      <Row>
        {categories.map((c) => (
          <Chip key={c.id} label={c.name} selected={c.id === form.category} onPress={() => setForm({ ...form, category: c.id })} />
        ))}
      </Row>
      <Field label={t('venueName')} value={form.name} onChangeText={(name) => setForm({ ...form, name })} />
      <Field label={t('address')} value={form.address} onChangeText={(address) => setForm({ ...form, address })} />
      <Field label={t('venuePhone')} value={form.phone} onChangeText={(phone) => setForm({ ...form, phone })} keyboardType="phone-pad" />
      <Card>
        <Subtitle>{t('coordinates')}</Subtitle>
        <Button title={t('useMyLocation')} variant="secondary" small onPress={useLocation} />
        <Row>
          <View style={{ flex: 1 }}>
            <Field label="lat" value={form.lat} onChangeText={(lat) => setForm({ ...form, lat })} keyboardType="decimal-pad" placeholder="41.311081" />
          </View>
          <View style={{ flex: 1 }}>
            <Field label="lng" value={form.lng} onChangeText={(lng) => setForm({ ...form, lng })} keyboardType="decimal-pad" placeholder="69.279737" />
          </View>
        </Row>
      </Card>
      <Muted>{t('venuePending')}</Muted>
      {error ? <ErrorBox message={error} /> : null}
      <Button title={t('createAndSend')} onPress={submit} loading={busy} disabled={!valid} />
    </Screen>
  );
}
