import { router } from 'expo-router';
import { useEffect, useState } from 'react';

import { api, errorMessage } from '@/api/client';
import type { Category, VenueListItem } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { Button, Card, Chip, Empty, ErrorBox, Field, Muted, notify, Row, Screen, Subtitle } from '@/components/ui';

export default function JoinVenueScreen() {
  const { t, setMode } = useAuth();
  const [categories, setCategories] = useState<Category[]>([]);
  const [category, setCategory] = useState<number | null>(null);
  const [query, setQuery] = useState('');
  const [venues, setVenues] = useState<VenueListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);

  useEffect(() => {
    api<Category[]>('categories', { auth: false }).then((data) => {
      setCategories(data);
      if (data[0]) setCategory(data[0].id);
    });
  }, []);

  useEffect(() => {
    if (!category) return;
    const handle = setTimeout(() => {
      api<VenueListItem[]>('venues', { auth: false, query: { category, q: query.trim() } })
        .then((data) => {
          setVenues(data);
          setError(null);
        })
        .catch((err) => setError(errorMessage(err)));
    }, 300);
    return () => clearTimeout(handle);
  }, [category, query]);

  async function join(venue: VenueListItem) {
    setBusy(venue.id);
    try {
      await api(`pro/venues/${venue.id}/join`, { method: 'POST' });
      await setMode('pro');
      notify(t('joinSent'));
      router.replace('/pro');
    } catch (err) {
      notify(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Screen>
      <Row>
        {categories.map((c) => (
          <Chip key={c.id} label={c.name} selected={c.id === category} onPress={() => setCategory(c.id)} />
        ))}
      </Row>
      <Field value={query} onChangeText={setQuery} placeholder={t('search')} />
      {error ? <ErrorBox message={error} /> : null}
      {venues.length === 0 ? <Empty text={t('noVenues')} /> : null}
      {venues.map((venue) => (
        <Card key={venue.id}>
          <Subtitle>{venue.name}</Subtitle>
          <Muted>{venue.address}</Muted>
          <Button title={t('join')} small onPress={() => join(venue)} loading={busy === venue.id} />
        </Card>
      ))}
      <Button title={t('createVenue')} variant="secondary" onPress={() => router.replace('/create-venue')} />
    </Screen>
  );
}
