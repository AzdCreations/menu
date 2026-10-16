import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

// Токены: на телефоне — в защищённом хранилище, в браузере (веб-панель) — в localStorage.
export const storage = {
  async get(key: string): Promise<string | null> {
    if (Platform.OS === 'web') {
      try {
        return globalThis.localStorage?.getItem(key) ?? null;
      } catch {
        return null;
      }
    }
    return SecureStore.getItemAsync(key);
  },
  async set(key: string, value: string): Promise<void> {
    if (Platform.OS === 'web') {
      try {
        globalThis.localStorage?.setItem(key, value);
      } catch {
        // приватный режим браузера — токен живёт до перезагрузки
      }
      return;
    }
    await SecureStore.setItemAsync(key, value);
  },
  async remove(key: string): Promise<void> {
    if (Platform.OS === 'web') {
      try {
        globalThis.localStorage?.removeItem(key);
      } catch {
        // нечего удалять
      }
      return;
    }
    await SecureStore.deleteItemAsync(key);
  },
};
