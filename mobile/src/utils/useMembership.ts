import { api, ApiError } from '@/api/client';
import type { Membership } from '@/api/types';
import { useApi } from './useApi';

/** Текущее членство специалиста; null — ещё не состоит ни в одном заведении. */
export function useMembership() {
  return useApi<Membership | null>(async () => {
    try {
      return await api<Membership>('pro/membership');
    } catch (err) {
      if (err instanceof ApiError && err.code === 'no_membership') return null;
      throw err;
    }
  });
}
