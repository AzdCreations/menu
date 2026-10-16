import { router } from 'expo-router';

import type { Membership } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { venueStatusLabel } from '@/i18n';
import { Button, Card, Muted, Notice, Screen, Title } from './ui';

/** Специалист без заведения: найти и вступить или создать новое. */
export function ProWelcome() {
  const { t } = useAuth();
  return (
    <Screen>
      <Title>{t('proWelcome')}</Title>
      <Muted>{t('proWelcomeHint')}</Muted>
      <Card>
        <Button title={t('findVenue')} onPress={() => router.push('/join-venue')} />
        <Button title={t('createVenue')} variant="secondary" onPress={() => router.push('/create-venue')} />
      </Card>
    </Screen>
  );
}

/** Предупреждения о статусе членства и заведения. */
export function MembershipNotice({ membership }: { membership: Membership }) {
  const { t, lang } = useAuth();
  if (membership.status === 'pending') return <Notice text={`${membership.venue.name}: ${t('membershipPending')}`} tone="warning" />;
  const status = membership.venue.status;
  if (status === 'pending') return <Notice text={t('venuePending')} tone="warning" />;
  if (status === 'rejected' || status === 'blocked') {
    return <Notice text={`${membership.venue.name}: ${venueStatusLabel(lang, status)}`} tone="danger" />;
  }
  return null;
}
