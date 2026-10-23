import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { MaterialFormDialog } from '@/components/settings/MaterialFormDialog';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { materialsKey } from '@/hooks/useMaterials';
import { useOptimisticMutation } from '@/hooks/useOptimisticMutation';
import { updateMaterial } from '@/services/adminApi';
import type { Material, MaterialFields } from '@/types/auth';
import type { Cuf } from '@/types/cuf';

const FIELDS = ['noc', 'part_number', 'ncage', 'grupo_clase'] as const;

/** The CUF's data (an admin edits it, optimistic: HR20) and its family:
 *  the CUF it was copied from and its variants. */
export function CufDataCard({ material, cuf, isAdmin }: { material: Material; cuf: Cuf; isAdmin: boolean }): React.JSX.Element {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  const update = useOptimisticMutation<Material, MaterialFields, Material>({
    queryKey: materialsKey,
    mutationFn: (fields) => updateMaterial(material.id, material.version, fields),
    apply: (list, fields) => list.map((m) => (m.id === material.id ? { ...m, ...fields } : m)),
    settle: (list, saved) => list.map((m) => (m.id === saved.id ? saved : m)),
  });
  return (
    <Card data-testid="cuf-data">
      <CardHeader className="flex flex-row items-start justify-between gap-2">
        <div className="flex flex-col gap-1">
          <CardDescription>{t('cuf.data')}</CardDescription>
          <CardTitle className="text-xl">{material.name}</CardTitle>
        </div>
        {isAdmin ? (
          <Button variant="outline" size="sm" onClick={() => setEditing(true)} data-testid="cuf-edit">
            {t('actions.edit')}
          </Button>
        ) : null}
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {material.description ? <p className="text-sm whitespace-pre-wrap">{material.description}</p> : null}
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {FIELDS.map((field) => (
            <div key={field}>
              <dt className="text-sm text-muted-foreground">{t(`material.fields.${field}`)}</dt>
              <dd className="font-mono text-sm">{material[field] ?? t('material.empty')}</dd>
            </div>
          ))}
        </dl>
        <div className="flex flex-col gap-1 text-sm" data-testid="cuf-family">
          <p>
            <span className="text-muted-foreground">{t('cuf.variantOf')}: </span>
            {cuf.copied_from ? (
              <Link to={`/materiales/${cuf.copied_from.id}/ficha`} className="text-link underline-offset-2 hover:underline">
                {cuf.copied_from.name}
              </Link>
            ) : (
              t('material.empty')
            )}
          </p>
          <p>
            <span className="text-muted-foreground">{t('cuf.variants')}: </span>
            {cuf.variants.length
              ? cuf.variants.map((v, i) => (
                  <span key={v.id}>
                    {i ? ', ' : ''}
                    <Link to={`/materiales/${v.id}/ficha`} className="text-link underline-offset-2 hover:underline">
                      {v.name}
                    </Link>
                  </span>
                ))
              : t('material.empty')}
          </p>
        </div>
      </CardContent>
      <MaterialFormDialog
        open={editing}
        material={material}
        onOpenChange={setEditing}
        onSubmit={(fields) => {
          update.mutate(fields);
          setEditing(false);
        }}
      />
    </Card>
  );
}
