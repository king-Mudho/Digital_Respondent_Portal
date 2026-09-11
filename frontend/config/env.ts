// Env-driven constants -- never hardcode the domain or API base URL inside
// components (docs/24_ENVIRONMENT_CONFIGURATION.md, AGENTS.md ground rule 9).

export const APP_DOMAIN =
  process.env.NEXT_PUBLIC_APP_DOMAIN ?? "research.agribizframework.com";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export const APP_ENV = process.env.NEXT_PUBLIC_APP_ENV ?? "development";
