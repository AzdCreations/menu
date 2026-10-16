import { Redirect, router, Slot, usePathname } from 'expo-router';
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { useAuth } from '@/auth/AuthContext';
import { Button, colors, Loading, Muted, Screen, Title } from '@/components/ui';

const NAV = [
  { href: '/admin', label: 'Модерация' },
  { href: '/admin/venues', label: 'Заведения' },
  { href: '/admin/users', label: 'Пользователи' },
  { href: '/admin/categories', label: 'Направления' },
  { href: '/admin/bookings', label: 'Записи' },
  { href: '/admin/stats', label: 'Статистика' },
  { href: '/admin/settings', label: 'Настройки' },
  { href: '/admin/audit', label: 'Журнал' },
] as const;

/** Веб-панель главного админа: боковое меню + текущий раздел. */
export default function AdminLayout() {
  const { status, user, logout } = useAuth();
  const pathname = usePathname();
  const { width } = useWindowDimensions();
  const wide = width >= 900;

  if (status === 'loading') return <Loading />;
  if (status === 'guest') return <Redirect href="/login" />;
  if (!user?.is_staff) {
    return (
      <Screen>
        <Title>Нет доступа</Title>
        <Muted>Веб-панель доступна только главному админу.</Muted>
        <Button title="Выйти" variant="secondary" onPress={logout} />
      </Screen>
    );
  }

  return (
    <View style={[styles.shell, { flexDirection: wide ? 'row' : 'column' }]}>
      <View style={[styles.nav, wide ? styles.navWide : styles.navNarrow]}>
        {wide ? <Text style={styles.brand}>Bron · Админ</Text> : null}
        {NAV.map((item) => {
          const active = item.href === '/admin' ? pathname === '/admin' : pathname.startsWith(item.href);
          return (
            <Pressable key={item.href} onPress={() => router.navigate(item.href)} style={[styles.navItem, active && styles.navItemActive]}>
              <Text style={[styles.navText, active && styles.navTextActive]}>{item.label}</Text>
            </Pressable>
          );
        })}
        <Pressable style={styles.navItem} onPress={logout}>
          <Text style={[styles.navText, { color: colors.danger }]}>Выйти</Text>
        </Pressable>
      </View>
      <View style={{ flex: 1 }}>
        <Slot />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  shell: { flex: 1, backgroundColor: colors.bg },
  nav: { backgroundColor: colors.card, borderColor: colors.border, gap: 4, padding: 12 },
  navWide: { width: 220, borderRightWidth: 1 },
  navNarrow: { flexDirection: 'row', flexWrap: 'wrap', borderBottomWidth: 1 },
  brand: { fontSize: 18, fontWeight: '700', color: colors.text, marginBottom: 12, paddingHorizontal: 10 },
  navItem: { paddingHorizontal: 10, paddingVertical: 9, borderRadius: 8 },
  navItemActive: { backgroundColor: colors.primarySoft },
  navText: { fontSize: 15, color: colors.text },
  navTextActive: { color: colors.primary, fontWeight: '600' },
});
