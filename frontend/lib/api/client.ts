import { API_BASE_URL } from "@/config/env";

/**
 * Uniform error envelope from the backend -- see
 * docs/06_API_ARCHITECTURE.md and backend/api/exceptions.py.
 */
export class ApiError extends Error {
  code: string;
  fieldErrors: Record<string, unknown>;
  status: number;

  constructor(
    status: number,
    code: string,
    message: string,
    fieldErrors: Record<string, unknown> = {},
  ) {
    super(message);
    this.status = status;
    this.code = code;
    this.fieldErrors = fieldErrors;
  }
}

interface RequestOptions extends RequestInit {
  /** JWT bearer token for internal (authenticated) endpoints. */
  authToken?: string;
}

export async function apiFetch<T>(
  path: string,
  { authToken, headers, ...init }: RequestOptions = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      ...headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const error = body?.error;
    throw new ApiError(
      response.status,
      error?.code ?? "unknown_error",
      error?.message ?? response.statusText,
      error?.field_errors ?? {},
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}
