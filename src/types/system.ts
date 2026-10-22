// The shapes of GET /api/health and GET /api/version
// (backend/app/schemas/system.py).

export interface MigrationStatus {
  current: string | null;
  head: string | null;
  up_to_date: boolean;
}

export interface HealthResponse {
  status: string;
  database: {
    status: string;
    migrations: MigrationStatus;
  };
}

export interface VersionResponse {
  app: string;
  aacf: string | null;
}
