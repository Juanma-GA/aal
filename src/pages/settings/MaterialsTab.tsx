import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { MoreHorizontal, Plus } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ConfirmDialog } from '@/components/settings/ConfirmDialog';
import { MaterialFormDialog } from '@/components/settings/MaterialFormDialog';
import { MembersSheet } from '@/components/settings/MembersSheet';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { materialsKey } from '@/hooks/useMaterials';
import { useOptimisticMutation } from '@/hooks/useOptimisticMutation';
import { notifyError } from '@/lib/notify';
import { createMaterial, deleteMaterial, fetchMaterials, updateMaterial } from '@/services/adminApi';
import type { Material, MaterialFields } from '@/types/auth';

/** A stored NOC / NCAGE, with a warning when it lacks its format (saved
 *  before the check existed: never corrected silently). */
function CodeCell({ value, invalid, hint }: { value: string | null; invalid: boolean; hint: string }): React.JSX.Element {
  const { t } = useTranslation();
  if (value === null) return <>{t('material.empty')}</>;
  return (
    <span className="inline-flex items-center gap-2">
      {value}
      {invalid ? (
        <Badge variant="outline" className="border-warning text-warning font-sans" title={hint} data-testid="format-warning">
          {t('settings.materials.invalidFormat')}
        </Badge>
      ) : null}
    </span>
  );
}

export function MaterialsTab(): React.JSX.Element {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  // An admin's list of materials is every material.
  const materials = useQuery({ queryKey: materialsKey, queryFn: fetchMaterials });
  const [editing, setEditing] = useState<Material | null | undefined>(undefined);
  const [deleting, setDeleting] = useState<Material | null>(null);
  const [members, setMembers] = useState<Material | null>(null);

  const edit = useOptimisticMutation<Material, { material: Material; fields: MaterialFields }, Material>({
    queryKey: materialsKey,
    mutationFn: ({ material, fields }) => updateMaterial(material.id, material.version, fields),
    apply: (list, { material, fields }) => list.map((m) => (m.id === material.id ? { ...m, ...fields } : m)),
    settle: (list, saved) => list.map((m) => (m.id === saved.id ? saved : m)),
  });
  const remove = useOptimisticMutation<Material, Material, void>({
    queryKey: materialsKey,
    mutationFn: (material) => deleteMaterial(material.id),
    apply: (list, material) => list.filter((m) => m.id !== material.id),
  });
  // Not optimistic: the id comes from the server (HR20's exception).
  const create = useMutation({
    mutationFn: createMaterial,
    onSuccess: (created) => {
      queryClient.setQueryData<Material[]>(materialsKey, (list) => [...(list ?? []), created].sort((a, b) => a.name.localeCompare(b.name)));
      setEditing(undefined);
    },
    onError: (error) => notifyError(error, t),
  });

  const submit = (fields: MaterialFields) => {
    if (editing) {
      edit.mutate({ material: editing, fields });
      setEditing(undefined);
    } else {
      create.mutate(fields);
    }
  };

  if (materials.isPending) return <Skeleton className="h-40 w-full" />;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex">
        <Button className="ml-auto" onClick={() => setEditing(null)} data-testid="new-material">
          <Plus aria-hidden="true" />
          {t('settings.materials.new')}
        </Button>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t('material.fields.name')}</TableHead>
            <TableHead>{t('material.fields.noc')}</TableHead>
            <TableHead>{t('material.fields.part_number')}</TableHead>
            <TableHead>{t('material.fields.ncage')}</TableHead>
            <TableHead>
              <span className="sr-only">{t('actions.more')}</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {(materials.data ?? []).length === 0 ? (
            <TableRow>
              <TableCell colSpan={5} className="text-muted-foreground">
                {t('settings.materials.empty')}
              </TableCell>
            </TableRow>
          ) : (
            (materials.data ?? []).map((m) => (
              <TableRow key={m.id} data-testid={`material-row-${m.name}`}>
                <TableCell className="font-medium">{m.name}</TableCell>
                <TableCell className="font-mono">
                  <CodeCell value={m.noc} invalid={m.format_problems.includes('noc')} hint={t('validation.noc')} />
                </TableCell>
                <TableCell className="font-mono">{m.part_number ?? t('material.empty')}</TableCell>
                <TableCell className="font-mono">
                  <CodeCell value={m.ncage} invalid={m.format_problems.includes('ncage')} hint={t('validation.ncage')} />
                </TableCell>
                <TableCell className="text-right">
                  <Button variant="outline" size="sm" onClick={() => setMembers(m)} data-testid={`members-${m.name}`}>
                    {t('settings.materials.members')}
                  </Button>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" aria-label={t('actions.more')}>
                        <MoreHorizontal aria-hidden="true" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onSelect={() => setEditing(m)}>{t('actions.edit')}</DropdownMenuItem>
                      <DropdownMenuItem variant="destructive" onSelect={() => setDeleting(m)}>
                        {t('actions.delete')}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
      <MaterialFormDialog open={editing !== undefined} material={editing ?? null} onOpenChange={(open) => !open && setEditing(undefined)} onSubmit={submit} />
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={t('settings.materials.deleteTitle', { name: deleting?.name ?? '' })}
        description={t('settings.materials.deleteHint')}
        confirmLabel={t('actions.delete')}
        onConfirm={() => {
          if (deleting) remove.mutate(deleting);
          setDeleting(null);
        }}
      />
      <MembersSheet material={members} onClose={() => setMembers(null)} />
    </div>
  );
}
