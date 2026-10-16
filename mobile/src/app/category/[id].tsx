import * as Location from 'expo-location';
import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Image, View } from 'react-native';

import { api, errorMessage } from '@/api/client';
import type { VenueListItem } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { Card, Chip, Empty, ErrorBox, Field, Loading, Muted, Row, Screen, Subtitle } from '@/components/ui';

type Coords = { lat: number; lng: number };

export default function VenuesScreen() {
  const { id, name } = useLocalSearchParams<{ id: string; name?: string }>();
  const { t } = useAuth();
  const [query, setQuery] = useState('');
  const [coords, setCoords] = useState<Coords | null>(null);
  const [venues, setVenues] = useState<VenueListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handle = setTimeout(async () => {
      try {
        const data = await api<VenueListItem[]>('venues', {
          auth: false,
          query: { category: id, q: query.trim(), lat: coords?.lat, lng: coords?.lng },
        });
        setVenues(data);
        setError(null);
      } catch (err) {
        setError(errorMessage(err));
      }
    }, 300);
    return () => clearTimeout(handle);
  }, [id, query, coords]);

  async function toggleNearby() {
    if (coords) return setCoords(null);
    try {
      const permission = await Location.requestForegroundPermissionsAsync();
      if (!permission.granted) return;
      const position = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      setCoords({ lat: position.coords.latitude, lng: position.coords.longitude });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <Screen>
      <Stack.Screen options={{ title: name ?? t('venuesNearby') }} />
      <Field value={query} onChangeText={setQuery} placeholder={t('search')} />
      <Row>
        <Chip label={t('nearMe')} selected={!!coords} onPress={toggleNearby} />
      </Row>
      {error ? <ErrorBox message={error} /> : null}
      {venues === null && !error ? <Loading /> : null}
      {venues?.length === 0 ? <Empty text={t('noVenues')} /> : null}
      {venues?.map((venue) => (
        <Card key={venue.id} onPress={() => router.push({ pathname: '/venue/[id]', params: { id: venue.id } })}>
          {venue.cover ? (
            <Image source={{ uri: venue.cover }} style={{ width: '100%', height: 140, borderRadius: 10 }} resizeMode="cover" />
          ) : null}
          <View style={{ gap: 2 }}>
            <Subtitle>{venue.name}</Subtitle>
            <Muted>{venue.address}</Muted>
            {venue.distance_km !== null ? <Muted>{`${venue.distance_km} ${t('kmAway')}`}</Muted> : null}
          </View>
        </Card>
      ))}
    </Screen>
  );
}
