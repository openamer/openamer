/** Fetch helpers shared by the web client. */

export interface ApiOptions {
  baseUrl: string;
  retries?: number;
  timeoutMs?: number;
}

const DEFAULT_RETRIES = 3;

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function fetchWithRetry(
  path: string,
  options: ApiOptions,
): Promise<Response> {
  const retries = options.retries ?? DEFAULT_RETRIES;
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    const response = await fetch(`${options.baseUrl}${path}`);
    if (response.ok) {
      return response;
    }
    if (attempt === retries) {
      throw new ApiError(response.status, `request failed: ${path}`);
    }
  }
  throw new ApiError(0, 'unreachable');
}
