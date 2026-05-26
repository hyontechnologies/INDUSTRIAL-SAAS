import { useAuthStore } from '../stores/useAuthStore';

const BASE_URL = '/api/v1';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const { token } = useAuthStore.getState();

  const headers = new Headers(options.headers);
  headers.set('Content-Type', 'application/json');

  if (token) {
    // Backend supports either X-API-Key or Authorization header
    headers.set('X-API-Key', token);
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let message = 'API request failed';
    try {
      const errData = await response.json();
      message = errData.message || errData.detail || message;
    } catch {
      // Ignored
    }
    throw new ApiError(response.status, message);
  }

  return response.json();
}
