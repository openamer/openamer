/** Thin client wrapper around the fetch helpers. */

import { type ApiOptions, fetchWithRetry } from './api';

export interface Client {
  get(path: string): Promise<Response>;
}

export function createClient(options: ApiOptions): Client {
  return {
    get(path: string): Promise<Response> {
      return fetchWithRetry(path, options);
    },
  };
}

export const defaultClient = createClient({ baseUrl: '/api' });
