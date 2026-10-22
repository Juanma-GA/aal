import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { MoreHorizontal, Plus } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ConfirmDialog } from '@/components/settings/ConfirmDialog';
import { TemporaryPasswordDialog } from '@/components/settings/TemporaryPasswordDialog';
import { UserFormDialog, type UserFormValues } from '@/components/settings/UserFormDialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useOptimisticMutation } from '@/hooks/useOptimisticMutation';
import { useMe } from '@/hooks/useSession';
import { catalogLabel } from '@/lib/labels';
import { notifyError } from '@/lib/notify';
import { createUser, deleteUser, fetchUsers, resetPassword, updateUser } from '@/services/adminApi';
import type { User } from '@/types/auth';

const usersKey = ['users'] as const;

type Edit = Partial<Pick<User, 'display_name' | 'is_admin' | 'is_active'>>;

export function UsersTab(): React.JSX.Element {
  const { t } = useTranslation();
  const me = useMe();
  const queryClient = useQueryClient();
  const users = useQuery({ queryKey: usersKey, queryFn: fetchUsers });
  const [search, setSearch] = useState('');
  const [editing, setEditing] = useState<User | null | undefined>(undefined); // undefined: closed, null: new
  const [confirm, setConfirm] = useState<{ kind: 'delete' | 'reset'; user: User } | null>(null);
  const [temporary, setTemporary] = useState<{ name: string; password: string } | null>(null);

  const edit = useOptimisticMutation<User, { user: User; changes: Edit }, User>({
    queryKey: usersKey,
    mutationFn: ({ user, changes }) => updateUser(user.id, user.version, changes),
    apply: (list, { user, changes }) => list.map((u) => (u.id === user.id ? { ...u, ...changes } : u)),
    settle: (list, saved) => list.map((u) => (u.id === saved.id ? saved : u)),
  });
  const remove = useOptimisticMutation<User, User, void>({
    queryKey: usersKey,
    mutationFn: (user) => deleteUser(user.id),
    apply: (list, user) => list.filter((u) => u.id !== user.id),
  });
  // Creating and resetting are not optimistic: the id and the temporary
  // password come from the server (the documented exception of HR20).
  const create = useMutation({
    mutationFn: createUser,
    onSuccess: (created) => {
      queryClient.setQueryData<User[]>(usersKey, (list) => [...(list ?? []), created.user]);
      setEditing(undefined);
      setTemporary({ name: created.user.display_name, password: created.temporary_password });
    },
    onError: (error) => notifyError(error, t),
  });
  const reset = useMutation({
    mutationFn: (user: User) => resetPassword(user.id),
    onSuccess: (result) => {
      queryClient.setQueryData<User[]>(usersKey, (list) => (list ?? []).map((u) => (u.id === result.user.id ? { ...u, ...result.user } : u)));
      setTemporary({ name: result.user.display_name, password: result.temporary_password });
    },
    onError: (error) => notifyError(error, t),
  });

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (users.data ?? []).filter((u) => !q || u.email.includes(q) || u.display_name.toLowerCase().includes(q));
  }, [users.data, search]);

  const submit = (values: UserFormValues) => {
    if (editing) {
      edit.mutate({ user: editing, changes: { display_name: values.display_name, is_admin: values.is_admin } });
      setEditing(undefined);
    } else {
      create.mutate(values);
    }
  };

  if (users.isPending) return <Skeleton className="h-40 w-full" />;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          className="max-w-sm"
          placeholder={t('settings.users.search')}
          aria-label={t('settings.users.search')}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <span className="text-sm text-muted-foreground">{t('settings.users.count', { count: filtered.length })}</span>
        <Button className="ml-auto" onClick={() => setEditing(null)} data-testid="new-user">
          <Plus aria-hidden="true" />
          {t('settings.users.new')}
        </Button>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t('settings.users.name')}</TableHead>
            <TableHead>{t('settings.users.email')}</TableHead>
            <TableHead>{t('settings.users.type')}</TableHead>
            <TableHead>{t('settings.users.state')}</TableHead>
            <TableHead>{t('settings.users.materials')}</TableHead>
            <TableHead>
              <span className="sr-only">{t('actions.more')}</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.length === 0 ? (
            <TableRow>
              <TableCell colSpan={6} className="text-muted-foreground">
                {t('settings.users.empty')}
              </TableCell>
            </TableRow>
          ) : (
            filtered.map((user) => (
              <TableRow key={user.id} data-testid={`user-row-${user.email}`}>
                <TableCell className="font-medium">{user.display_name}</TableCell>
                <TableCell>{user.email}</TableCell>
                <TableCell>{user.is_admin ? <Badge>{t('settings.users.admin')}</Badge> : t('settings.users.user')}</TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    <Badge variant={user.is_active ? 'secondary' : 'outline'}>
                      {user.is_active ? t('settings.users.active') : t('settings.users.inactive')}
                    </Badge>
                    {user.must_change_password ? <Badge variant="outline">{t('settings.users.pendingChange')}</Badge> : null}
                  </div>
                </TableCell>
                <TableCell className="whitespace-normal">
                  {user.materials.length
                    ? user.materials.map((m) => `${m.material_name} (${catalogLabel(t, 'roles', m.role)})`).join(', ')
                    : t('settings.users.none')}
                </TableCell>
                <TableCell className="text-right">
                  {user.id === me.data?.id ? null : (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" aria-label={t('actions.more')}>
                          <MoreHorizontal aria-hidden="true" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onSelect={() => setEditing(user)}>{t('actions.edit')}</DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => edit.mutate({ user, changes: { is_active: !user.is_active } })}>
                          {user.is_active ? t('settings.users.deactivate') : t('settings.users.reactivate')}
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => setConfirm({ kind: 'reset', user })}>{t('settings.users.resetPassword')}</DropdownMenuItem>
                        <DropdownMenuItem variant="destructive" onSelect={() => setConfirm({ kind: 'delete', user })}>
                          {t('actions.delete')}
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  )}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      <UserFormDialog open={editing !== undefined} user={editing ?? null} onOpenChange={(open) => !open && setEditing(undefined)} onSubmit={submit} />
      <ConfirmDialog
        open={confirm !== null}
        onOpenChange={(open) => !open && setConfirm(null)}
        title={
          confirm?.kind === 'delete'
            ? t('settings.users.deleteTitle', { name: confirm.user.display_name })
            : t('settings.users.resetTitle', { name: confirm?.user.display_name ?? '' })
        }
        description={confirm?.kind === 'delete' ? t('settings.users.deleteHint') : t('settings.users.resetHint')}
        confirmLabel={confirm?.kind === 'delete' ? t('actions.delete') : t('settings.users.resetPassword')}
        onConfirm={() => {
          if (confirm?.kind === 'delete') remove.mutate(confirm.user);
          else if (confirm) reset.mutate(confirm.user);
          setConfirm(null);
        }}
      />
      <TemporaryPasswordDialog name={temporary?.name ?? ''} password={temporary?.password ?? null} onClose={() => setTemporary(null)} />
    </div>
  );
}
