import type { Me, TokenResponse, UiPreferences } from '@/types/auth';
import { useAuthStore } from '@/stores/authStore';
import { apiFetchJson, apiSend } from './apiClient';

export async function login(email: string, password: string): Promise<void> {
  const token = await apiSend<TokenResponse>('POST', '/auth/login', { email, password });
  useAuthStore.getState().signIn(token.access_token);
}

export async function logout(): Promise<void> {
  try {
    await apiSend<void>('POST', '/auth/logout');
  } finally {
    useAuthStore.getState().signOut();
  }
}

export function fetchMe(): Promise<Me> {
  return apiFetchJson<Me>('/auth/me');
}

/** The answer opens a new session (the server ends every other one). */
export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  const token = await apiSend<TokenResponse>('POST', '/me/password', {
    current_password: currentPassword,
    new_password: newPassword,
  });
  useAuthStore.getState().signIn(token.access_token);
}

export function updateUiPreferences(patch: UiPreferences): Promise<Me> {
  return apiSend<Me>('PUT', '/me/ui-preferences', patch);
}
