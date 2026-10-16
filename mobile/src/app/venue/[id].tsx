import { router, Stack, useLocalSearchParams } from 'expo-router';
import { Image, Linking, Pressable, ScrollView, Text, View } from 'react-native';

import { api } from '@/api/client';
import type { PublicService, PublicSpecialist, VenueDetail } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { Button, Card, colors, Empty, ErrorBox, Loading, Muted, Row, Screen, Subtitle, Title } from '@/components/ui';
import { formatDuration, formatPrice, WEEKDAYS } from '@/utils/format';
import { useApi } from '@/utils/useApi';

export default function VenueScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t, lang } = useAuth();
  const { data: venue, error, loading, reload } = useApi(() => api<VenueDetail>(`venues/${id}`, { auth: false }), [id]);

  if (loading) return <Loading />;
  if (error || !venue) return <Screen><ErrorBox message={error ?? ''} onRetry={reload} retryLabel={t('retry')} /></Screen>;

  function openBooking(specialist: PublicSpecialist, service: PublicService) {
    router.push({
      pathname: '/book',
      params: {
        membership: specialist.id,
        service: service.id,
        venue: venue!.id,
        specialistName: specialist.name,
        serviceName: service.name,
        duration: service.duration_minutes,
      },
    });
  }

  return (
    <Screen>
      <Stack.Screen options={{ title: venue.name }} />
      {venue.photos.length ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
          {venue.photos.map((photo) => (
            <Image key={photo.id} source={{ uri: photo.image }} style={{ width: 260, height: 170, borderRadius: 12 }} />
          ))}
        </ScrollView>
      ) : null}
      <Title>{venue.name}</Title>
      <Muted>{venue.address}</Muted>
      <Row>
        {venue.phone ? <Button small variant="secondary" title={`${t('call')} ${venue.phone}`} onPress={() => Linking.openURL(`tel:${venue.phone}`)} /> : null}
        <Button
          small
          variant="secondary"
          title={t('onMap')}
          onPress={() => Linking.openURL(`https://maps.google.com/?q=${venue.lat},${venue.lng}`)}
        />
      </Row>

      <Card>
        <Subtitle>{t('hours')}</Subtitle>
        {venue.hours.map((h) => (
          <Row key={h.weekday} style={{ justifyContent: 'space-between' }}>
            <Text>{WEEKDAYS[lang][h.weekday]}</Text>
            <Muted>{h.is_day_off ? t('dayOff') : `${h.start?.slice(0, 5)} – ${h.end?.slice(0, 5)}`}</Muted>
          </Row>
        ))}
      </Card>

      <Subtitle>{t('specialists')}</Subtitle>
      {venue.specialists.length === 0 ? <Empty text={t('empty')} /> : null}
      {venue.specialists.map((specialist) => (
        <Card key={specialist.id}>
          <Row>
            {specialist.photo ? <Image source={{ uri: specialist.photo }} style={{ width: 44, height: 44, borderRadius: 22 }} /> : null}
            <View style={{ flex: 1 }}>
              <Subtitle>{specialist.name}</Subtitle>
              <Muted>{venue.specialist_name}</Muted>
            </View>
          </Row>
          {specialist.bio ? <Muted>{specialist.bio}</Muted> : null}
          {specialist.services.map((service) => (
            <Pressable
              key={service.id}
              onPress={() => openBooking(specialist, service)}
              style={({ pressed }) => ({
                flexDirection: 'row',
                justifyContent: 'space-between',
                alignItems: 'center',
                paddingVertical: 10,
                borderTopWidth: 1,
                borderTopColor: colors.border,
                opacity: pressed ? 0.6 : 1,
              })}
            >
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 15, color: colors.text }}>{service.name}</Text>
                <Muted>{formatDuration(service.duration_minutes, lang)}</Muted>
              </View>
              <View style={{ alignItems: 'flex-end' }}>
                {service.price !== null ? <Text style={{ fontWeight: '600' }}>{formatPrice(service.price, service.price_from, lang)}</Text> : null}
                <Text style={{ color: colors.primary, fontWeight: '600' }}>{t('book')} ›</Text>
              </View>
            </Pressable>
          ))}
        </Card>
      ))}
    </Screen>
  );
}
