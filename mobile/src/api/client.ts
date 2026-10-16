import { storage } from './storage';

export const API_URL = (process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1').replace(/\/$/, '');

const ACCESS_KEY = 'auth.access';
const REFRESH_KEY = 'auth.refresh';

export class ApiError extends Error {
  code: string;
  status: number;
  fields: Record<string, unknown>;

  constructor(status: number, code: string, message: string, fields: Record<string, unknown> = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

type Tokens = { access: string; refresh: string };

let tokens: Tokens | null = null;
let language = 'ru';
let onAuthLost: (() => void) | null = null;
let refreshing: Promise<boolean> | null = null;

export async function loadTokens(): Promise<boolean> {
  const [access, refresh] = await Promise.all([storage.get(ACCESS_KEY), storage.get(REFRESH_KEY)]);
  tokens = access && refresh ? { access, refresh } : null;
  return tokens !== null;
}

export async function saveTokens(next: Tokens | null): Promise<void> {
  tokens = next;
  if (next) {
    await Promise.all([storage.set(ACCESS_KEY, next.access), storage.set(REFRESH_KEY, next.refresh)]);
  } else {
    await Promise.all([storage.remove(ACCESS_KEY), storage.remove(REFRESH_KEY)]);
  }
}

export function getRefreshToken(): string | null {
  return tokens?.refresh ?? null;
}

export function setLanguage(lang: string) {
  language = lang;
}

export function setOnAuthLost(handler: (() => void) | null) {
  onAuthLost = handler;
}

async function refreshTokens(): Promise<boolean> {
  if (!tokens?.refresh) return false;
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const response = await fetch(`${API_URL}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh: tokens?.refresh }),
        });
        if (!response.ok) return false;
        const data = await response.json();
        await saveTokens({ access: data.access, refresh: data.refresh ?? tokens!.refresh });
        return true;
      } catch {
        return false;
      } finally {
        refreshing = null;
      }
    })();
  }
  return refreshing;
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  auth?: boolean;
};

function buildUrl(path: string, query?: RequestOptions['query']) {
  const url = `${API_URL}/${path.replace(/^\//, '')}`;
  if (!query) return url;
  const params = Object.entries(query)
    .filter(([, value]) => value !== undefined && value !== null && value !== '')
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
  return params.length ? `${url}?${params.join('&')}` : url;
}

export async function api<T = any>(path: string, options: RequestOptions = {}, retry = true): Promise<T> {
  const { method = 'GET', body, query, auth = true } = options;
  const isForm = typeof FormData !== 'undefined' && body instanceof FormData;
  const headers: Record<string, string> = { Accept: 'application/json', 'Accept-Language': language };
  if (body !== undefined && !isForm) headers['Content-Type'] = 'application/json';
  if (auth && tokens?.access) headers.Authorization = `Bearer ${tokens.access}`;

  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: body === undefined ? undefined : isForm ? (body as FormData) : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, 'network', 'Нет связи с сервером. Проверьте интернет.');
  }

  if (response.status === 401 && auth && tokens && retry) {
    if (await refreshTokens()) return api<T>(path, options, false);
    await saveTokens(null);
    onAuthLost?.();
  }

  if (response.status === 204) return undefined as T;
  const text = await response.text();
  const data = text ? safeJson(text) : null;
  if (!response.ok) {
    throw new ApiError(
      response.status,
      data?.code ?? 'error',
      data?.message || firstFieldError(data?.fields) || `Ошибка ${response.status}`,
      data?.fields ?? {},
    );
  }
  return data as T;
}

function safeJson(text: string) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function firstFieldError(fields: Record<string, unknown> | undefined): string | null {
  if (!fields) return null;
  for (const value of Object.values(fields)) {
    if (Array.isArray(value) && value.length) return String(value[0]);
    if (typeof value === 'string') return value;
  }
  return null;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const field = firstFieldError(error.fields as Record<string, unknown>);
    return field && error.code === 'validation_error' ? field : error.message;
  }
  return 'Что-то пошло не так. Попробуйте ещё раз.';
}
