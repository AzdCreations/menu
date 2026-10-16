// API отдаёт время в часовом поясе заведения (+05:00), поэтому дату и время
// берём прямо из строки ISO, без пересчёта в часовой пояс телефона.

export const WEEKDAYS = {
  ru: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
  uz: ['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'],
};

const MONTHS = {
  ru: ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'],
  uz: ['yan', 'fev', 'mar', 'apr', 'may', 'iyn', 'iyl', 'avg', 'sen', 'okt', 'noy', 'dek'],
};

export function isoTime(iso: string): string {
  return iso.slice(11, 16);
}

export function isoDate(iso: string): string {
  return iso.slice(0, 10);
}

/** Дата YYYY-MM-DD → «19 окт, Пн». */
export function formatDay(date: string, lang: 'ru' | 'uz' = 'ru'): string {
  const [y, m, d] = date.split('-').map(Number);
  const weekday = (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7;
  return `${d} ${MONTHS[lang][m - 1]}, ${WEEKDAYS[lang][weekday]}`;
}

export function formatDateTime(iso: string, lang: 'ru' | 'uz' = 'ru'): string {
  return `${formatDay(isoDate(iso), lang)} · ${isoTime(iso)}`;
}

export function formatPrice(price: number | null, from = false, lang: 'ru' | 'uz' = 'ru'): string {
  if (price === null || price === undefined) return '';
  const value = price.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  const prefix = from ? (lang === 'uz' ? 'dan ' : 'от ') : '';
  return lang === 'uz' ? `${value} so'm${from ? 'dan' : ''}` : `${prefix}${value} сум`;
}

export function formatDuration(minutes: number, lang: 'ru' | 'uz' = 'ru'): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  const hu = lang === 'uz' ? 'soat' : 'ч';
  const mu = lang === 'uz' ? 'daq' : 'мин';
  if (h && m) return `${h} ${hu} ${m} ${mu}`;
  return h ? `${h} ${hu}` : `${m} ${mu}`;
}

/** Даты на ближайшие N дней в Ташкенте (UTC+5), формат YYYY-MM-DD. */
export function nextDays(count: number): string[] {
  const now = new Date(Date.now() + 5 * 3600 * 1000);
  const result: string[] = [];
  for (let i = 0; i < count; i++) {
    const day = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + i));
    result.push(day.toISOString().slice(0, 10));
  }
  return result;
}

export function todayTashkent(): string {
  return nextDays(1)[0];
}

export function addDays(date: string, days: number): string {
  const [y, m, d] = date.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

/** Склейка даты и времени в ISO с поясом Ташкента. */
export function tashkentIso(date: string, time: string): string {
  return `${date}T${time}:00+05:00`;
}

export function minutesLeft(iso: string | null): number | null {
  if (!iso) return null;
  return Math.max(0, Math.ceil((new Date(iso).getTime() - Date.now()) / 60000));
}

export function normalizePhone(raw: string): string {
  const digits = raw.replace(/\D/g, '');
  return digits.length === 9 ? `+998${digits}` : `+${digits}`;
}
