const DEFAULT_API_BASE_URL = 'http://localhost:8000';

type ApiErrorOptions = {
  message: string;
  status: number;
};

export class ApiError extends Error {
  readonly status: number;

  constructor({ message, status }: ApiErrorOptions) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, '');
}

function getApiBaseUrl(): string {
  const envBase = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_BASE;
  if (!envBase) {
    return DEFAULT_API_BASE_URL;
  }

  return trimTrailingSlash(envBase);
}

export const API_BASE_URL = getApiBaseUrl();

export async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = new URL(path, API_BASE_URL);

  const response = await fetch(url.toString(), {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => '');
    throw new ApiError({
      status: response.status,
      message: errorText || `Request failed (${response.status})`,
    });
  }

  return (await response.json()) as T;
}
