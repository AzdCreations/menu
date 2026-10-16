import { Redirect, Tabs } from 'expo-router';

import { useAuth } from '@/auth/AuthContext';
import { tabIcon } from '@/components/TabIcon';
import { colors, Loading } from '@/components/ui';

export default function ProTabs() {
  const { status, t } = useAuth();
  if (status === 'loading') return <Loading />;
  if (status === 'guest') return <Redirect href="/login" />;
  return (
    <Tabs screenOptions={{ tabBarActiveTintColor: colors.primary, headerStyle: { backgroundColor: colors.card } }}>
      <Tabs.Screen
        name="index"
        options={{ title: t('tabSchedule'), tabBarIcon: tabIcon('calendar') }}
      />
      <Tabs.Screen
        name="services"
        options={{ title: t('tabServices'), tabBarIcon: tabIcon('list') }}
      />
      <Tabs.Screen
        name="venue"
        options={{ title: t('tabVenue'), tabBarIcon: tabIcon('business') }}
      />
      <Tabs.Screen
        name="profile"
        options={{ title: t('tabProfile'), tabBarIcon: tabIcon('person') }}
      />
    </Tabs>
  );
}
