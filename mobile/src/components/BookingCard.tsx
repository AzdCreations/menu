import { Text, View } from 'react-native';

import type { Booking, BookingStatus, Language } from '@/api/types';
import { bookingStatusLabel } from '@/i18n';
import { formatDateTime, formatPrice, isoTime, minutesLeft } from '@/utils/format';
import { Badge, Card, colors, Muted, Row, Subtitle } from './ui';

export function statusTone(status: BookingStatus): 'neutral' | 'success' | 'warning' | 'danger' | 'info' {
  switch (status) {
    case 'pending':
      return 'warning';
    case 'confirmed':
      return 'info';
    case 'completed':
      return 'success';
    case 'rejected':
    case 'cancelled_client':
    case 'cancelled_specialist':
    case 'no_show':
      return 'danger';
    default:
      return 'neutral';
  }
}

/** Карточка записи. forSpecialist — показывает клиента вместо заведения. */
export function BookingCard({
  booking,
  lang,
  forSpecialist = false,
  timeOnly = false,
  children,
}: {
  booking: Booking;
  lang: Language;
  forSpecialist?: boolean;
  timeOnly?: boolean;
  children?: React.ReactNode;
}) {
  const left = booking.status === 'pending' ? minutesLeft(booking.respond_by) : null;
  const isBlock = booking.kind === 'block';
  return (
    <Card style={isBlock ? { backgroundColor: colors.bg } : undefined}>
      <Row style={{ justifyContent: 'space-between' }}>
        <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>
          {timeOnly ? `${isoTime(booking.start)}–${isoTime(booking.end)}` : formatDateTime(booking.start, lang)}
        </Text>
        {!isBlock ? <Badge label={bookingStatusLabel(lang, booking.status)} tone={statusTone(booking.status)} /> : null}
      </Row>
      {isBlock ? (
        <Muted>{booking.comment || (lang === 'uz' ? 'Vaqt band' : 'Время занято')}</Muted>
      ) : forSpecialist ? (
        <View style={{ gap: 2 }}>
          <Subtitle>{booking.client_name || '—'}</Subtitle>
          {booking.client_phone ? <Muted>{booking.client_phone}</Muted> : null}
          <Muted>{[booking.service_name, booking.specialist_name].filter(Boolean).join(' · ')}</Muted>
        </View>
      ) : (
        <View style={{ gap: 2 }}>
          <Subtitle>{booking.venue_name}</Subtitle>
          <Muted>{`${booking.specialist_name} · ${booking.service_name}`}</Muted>
          <Muted>{booking.venue_address}</Muted>
        </View>
      )}
      {booking.price !== null && !isBlock ? <Muted>{formatPrice(booking.price, false, lang)}</Muted> : null}
      {booking.comment && !isBlock ? <Muted>{`«${booking.comment}»`}</Muted> : null}
      {Object.entries(booking.extra ?? {}).map(([key, value]) => (
        <Muted key={key}>{`${key}: ${String(value)}`}</Muted>
      ))}
      {booking.status_reason ? <Muted>{booking.status_reason}</Muted> : null}
      {left !== null ? <Badge label={`${left} ${lang === 'uz' ? 'daq javob uchun' : 'мин на ответ'}`} tone="warning" /> : null}
      {children}
    </Card>
  );
}
