import { router } from 'expo-router';
import { RefreshControl } from 'react-native';

import { api } from '@/api/client';
import type { Category } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { Card, Empty, ErrorBox, Loading, Muted, Screen, Subtitle, Title } from '@/components/ui';
import { useApi } from '@/utils/useApi';

export default function CategoriesScreen() {
  const { t } = useAuth();
  const { data, error, loading, refreshing, reload } = useApi(() => api<Category[]>('categories', { auth: false }));

  if (loading) return <Loading />;
  return (
    <Screen refreshControl={<RefreshControl refreshing={refreshing} onRefresh={reload} />}>
      <Title>{t('chooseCategory')}</Title>
      {error ? <ErrorBox message={error} onRetry={reload} retryLabel={t('retry')} /> : null}
      {data?.length === 0 ? <Empty text={t('empty')} /> : null}
      {data?.map((category) => (
        <Card key={category.id} onPress={() => router.push({ pathname: '/category/[id]', params: { id: category.id, name: category.name } })}>
          <Subtitle>{category.name}</Subtitle>
          <Muted>{category.specialist_name}</Muted>
        </Card>
      ))}
    </Screen>
  );
}
