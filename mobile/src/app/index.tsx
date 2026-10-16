import { Redirect } from 'expo-router';
import { Platform } from 'react-native';

import { useAuth } from '@/auth/AuthContext';
import { Loading } from '@/components/ui';

/** Точка входа: решает, куда отправить пользователя. */
export default function Index() {
  const { status, user, mode } = useAuth();
  if (status === 'loading') return <Loading />;
  if (status === 'guest' || !user) return <Redirect href="/login" />;
  if (user.is_staff && Platform.OS === 'web') return <Redirect href="/admin" />;
  if (!user.name || !user.pd_consent) return <Redirect href="/onboarding" />;
  return <Redirect href={mode === 'pro' ? '/pro' : '/client'} />;
}
