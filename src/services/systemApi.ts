import type { HealthResponse, VersionResponse } from '@/types/system';
import { apiFetchJson } from './apiClient';

export function fetchHealth(): Promise<HealthResponse> {
  return apiFetchJson<HealthResponse>('/health');
}

export function fetchVersion(): Promise<VersionResponse> {
  return apiFetchJson<VersionResponse>('/version');
}
