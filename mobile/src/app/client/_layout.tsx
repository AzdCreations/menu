import { Redirect, Tabs } from 'expo-router';

import { useAuth } from '@/auth/AuthContext';
import { tabIcon } from '@/components/TabIcon';
import { colors, Loading } from '@/components/ui';

export default function ClientTabs() {
  const { status, t } = useAuth();
  if (status === 'loading') return <Loading />;
  if (status === 'guest') return <Redirect href="/login" />;
  return (
    <Tabs screenOptions={{ tabBarActiveTintColor: colors.primary, headerStyle: { backgroundColor: colors.card } }}>
      <Tabs.Screen
        name="index"
        options={{ title: t('tabHome'), tabBarIcon: tabIcon('search') }}
      />
      <Tabs.Screen
        name="bookings"
        options={{ title: t('tabBookings'), tabBarIcon: tabIcon('calendar') }}
      />
      <Tabs.Screen
        name="profile"
        options={{ title: t('tabProfile'), tabBarIcon: tabIcon('person') }}
      />
    </Tabs>
  );
}
