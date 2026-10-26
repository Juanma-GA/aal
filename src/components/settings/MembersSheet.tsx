import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { DetailPanel } from '@/components/layout/DetailPanel';
import { ConfirmDialog } from '@/components/settings/ConfirmDialog';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { useOptimisticMutation } from '@/hooks/useOptimisticMutation';
import { catalogLabel } from '@/lib/labels';
import { assignMember, fetchMembers, fetchRoles, fetchUsers, removeMember } from '@/services/adminApi';
import type { Material, Member } from '@/types/auth';

interface Props {
  material: Material | null;
  onClose: () => void;
}

export function MembersSheet({ material, onClose }: Props): React.JSX.Element | null {
  const { t } = useTranslation();
  const materialId = material?.id ?? '';
  const key = ['materials', materialId, 'members'] as const;
  const members = useQuery({ queryKey: key, queryFn: () => fetchMembers(materialId), enabled: material !== null });
  const users = useQuery({ queryKey: ['users'], queryFn: fetchUsers, enabled: material !== null });
  const roles = useQuery({ queryKey: ['roles'], queryFn: fetchRoles, enabled: material !== null });
  const [newUser, setNewUser] = useState('');
  const [newRole, setNewRole] = useState('');
  const [removing, setRemoving] = useState<Member | null>(null);
  // The users list shows each user's materials: refreshed after a change.
  const invalidate = [['users'], ['materials']];

  const assign = useOptimisticMutation<Member, { userId: string; role: string }, Member>({
    queryKey: key,
    mutationFn: ({ userId, role }) => assignMember(materialId, userId, role),
    apply: (list, { userId, role }) => {
      if (list.some((m) => m.user_id === userId)) return list.map((m) => (m.user_id === userId ? { ...m, role } : m));
      const user = users.data?.find((u) => u.id === userId);
      return user ? [...list, { user_id: userId, email: user.email, display_name: user.display_name, role, assigned_at: new Date().toISOString() }] : list;
    },
    settle: (list, saved) => list.map((m) => (m.user_id === saved.user_id ? saved : m)),
    invalidate,
  });
  const remove = useOptimisticMutation<Member, Member, void>({
    queryKey: key,
    mutationFn: (member) => removeMember(materialId, member.user_id),
    apply: (list, member) => list.filter((m) => m.user_id !== member.user_id),
    invalidate,
  });

  const roleOptions = roles.data?.roles ?? [];
  const candidates = (users.data ?? []).filter((u) => !(members.data ?? []).some((m) => m.user_id === u.id));

  // A docked panel (E15): only while a material is chosen.
  if (!material) return null;
  return (
    <DetailPanel
      title={t('settings.materials.membersTitle', { name: material.name })} description={t('settings.materials.membersHint')}
      onClose={onClose} overlayClassName="sm:max-w-lg" testId="members-panel"
    >
        <div className="flex flex-col gap-4 px-4 pb-6">
          {members.isPending ? (
            <Skeleton className="h-24 w-full" />
          ) : members.data?.length ? (
            <ul className="flex flex-col gap-3" data-testid="members-list">
              {members.data.map((m) => (
                <li key={m.user_id} className="flex flex-wrap items-center gap-2" data-testid={`member-${m.email}`}>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">{m.display_name}</p>
                    <p className="truncate text-xs text-muted-foreground">{m.email}</p>
                  </div>
                  <Select value={m.role} onValueChange={(role) => assign.mutate({ userId: m.user_id, role })}>
                    <SelectTrigger className="w-36" aria-label={t('settings.materials.role')}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {roleOptions.map((r) => (
                        <SelectItem key={r.code} value={r.code}>
                          {catalogLabel(t, 'roles', r.code)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button variant="ghost" size="sm" onClick={() => setRemoving(m)}>
                    {t('actions.remove')}
                  </Button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">{t('settings.materials.noMembers')}</p>
          )}
          <Separator />
          <div className="flex flex-col gap-2">
            <h3 className="text-sm font-medium text-foreground">{t('settings.materials.addMember')}</h3>
            <Select value={newUser} onValueChange={setNewUser}>
              <SelectTrigger className="w-full" aria-label={t('settings.materials.user')} data-testid="member-user">
                <SelectValue placeholder={t('settings.materials.chooseUser')} />
              </SelectTrigger>
              <SelectContent>
                {candidates.map((u) => (
                  <SelectItem key={u.id} value={u.id}>
                    {u.display_name} · {u.email}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={newRole} onValueChange={setNewRole}>
              <SelectTrigger className="w-full" aria-label={t('settings.materials.role')} data-testid="member-role">
                <SelectValue placeholder={t('settings.materials.chooseRole')} />
              </SelectTrigger>
              <SelectContent>
                {roleOptions.map((r) => (
                  <SelectItem key={r.code} value={r.code}>
                    {catalogLabel(t, 'roles', r.code)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              disabled={!newUser || !newRole}
              onClick={() => {
                assign.mutate({ userId: newUser, role: newRole });
                setNewUser('');
                setNewRole('');
              }}
              data-testid="add-member"
            >
              {t('actions.add')}
            </Button>
          </div>
        </div>
      <ConfirmDialog
        open={removing !== null}
        onOpenChange={(open) => !open && setRemoving(null)}
        title={t('settings.materials.removeTitle', { name: removing?.display_name ?? '' })}
        description={t('settings.materials.removeHint')}
        confirmLabel={t('actions.remove')}
        onConfirm={() => {
          if (removing) remove.mutate(removing);
          setRemoving(null);
        }}
      />
    </DetailPanel>
  );
}
