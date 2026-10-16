import { Ionicons } from '@expo/vector-icons';
import type { ComponentProps } from 'react';

type IconName = ComponentProps<typeof Ionicons>['name'];

/** Иконка для вкладки: tabBarIcon={tabIcon('calendar')}. */
export function tabIcon(name: IconName) {
  return function TabBarIcon({ color, size }: { color: unknown; size: number }) {
    return <Ionicons name={name} color={String(color)} size={size} />;
  };
}
