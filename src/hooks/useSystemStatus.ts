import { useQuery } from '@tanstack/react-query';
import { fetchHealth, fetchVersion } from '@/services/systemApi';

export const systemKeys = {
  health: ['system', 'health'] as const,
  version: ['system', 'version'] as const,
};

export function useHealth() {
  return useQuery({ queryKey: systemKeys.health, queryFn: fetchHealth, retry: false });
}

export function useVersion() {
  return useQuery({ queryKey: systemKeys.version, queryFn: fetchVersion, retry: false });
}
