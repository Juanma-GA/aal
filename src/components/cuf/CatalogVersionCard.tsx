import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { cufKey } from '@/hooks/useCuf';
import { notifyError } from '@/lib/notify';
import { fetchCatalogVersions } from '@/services/catalogApi';
import { changeCatalogVersion, fetchImpact } from '@/services/cufApi';
import type { Cuf } from '@/types/cuf';

function CodeList({ title, codes, testId }: { title: string; codes: string[]; testId: string }): React.JSX.Element | null {
  if (!codes.length) return null;
  return (
    <div data-testid={testId}>
      <p className="text-sm font-medium">
        {title} ({codes.length})
      </p>
      <p className="max-h-24 overflow-auto font-mono text-xs text-muted-foreground">{codes.join(' · ')}</p>
    </div>
  );
}

/** The catalog version the CUF works with; an admin changes it after
 *  seeing the impact on its normalized configuration, and confirms. */
export function CatalogVersionCard({ cuf, isAdmin }: { cuf: Cuf; isAdmin: boolean }): React.JSX.Element {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [target, setTarget] = useState('');
  const versions = useQuery({ queryKey: ['catalog', 'versions'], queryFn: fetchCatalogVersions, enabled: open });
  const impact = useQuery({ queryKey: ['cuf', cuf.material_id, 'impact', target], queryFn: () => fetchImpact(cuf.material_id, target), enabled: Boolean(target) });
  const apply = useMutation({
    mutationFn: () => changeCatalogVersion(cuf.material_id, cuf.version, target),
    onSuccess: (saved) => {
      queryClient.setQueryData(cufKey(cuf.material_id), saved);
      void queryClient.invalidateQueries({ queryKey: ['cuf', cuf.material_id, 'tree'] });
      setOpen(false);
      setTarget('');
    },
    onError: (error) => notifyError(error, t, () => void queryClient.invalidateQueries({ queryKey: cufKey(cuf.material_id) })),
  });
  const v = cuf.catalog_version;
  return (
    <Card data-testid="cuf-catalog-version">
      <CardHeader>
        <CardTitle>{t('cuf.catalogVersion')}</CardTitle>
        <CardDescription>{t('cuf.catalogVersionHint')}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center gap-3">
        {v ? (
          <Link to={`/configuracion-funcional?v=${v.id}`} className="text-link underline-offset-2 hover:underline" data-testid="cuf-version-label">
            {t('catalog.versionLabel', { number: v.number, label: v.label })}
            {v.is_active ? ` · ${t('catalog.active')}` : ''}
          </Link>
        ) : (
          <span className="text-warning">{t('cuf.noCatalog')}</span>
        )}
        {isAdmin ? (
          <Button variant="outline" size="sm" onClick={() => setOpen(true)} data-testid="cuf-change-version">
            {t('cuf.changeVersion')}
          </Button>
        ) : null}
      </CardContent>
      <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) setTarget(''); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('cuf.changeVersionTitle')}</DialogTitle>
            <DialogDescription>{t('cuf.changeVersionHint')}</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3">
            <Label htmlFor="cuf-version-target">{t('catalog.version')}</Label>
            <Select value={target} onValueChange={setTarget}>
              <SelectTrigger id="cuf-version-target" className="w-full">
                <SelectValue placeholder={t('cuf.chooseVersion')} />
              </SelectTrigger>
              <SelectContent>
                {(versions.data ?? []).filter((x) => x.id !== v?.id).map((x) => (
                  <SelectItem key={x.id} value={x.id}>
                    {t('catalog.versionLabel', { number: x.number, label: x.label })}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {impact.data ? (
              <div className="flex flex-col gap-2 rounded-md border border-border p-3" data-testid="cuf-impact">
                <p className="text-sm">{t('cuf.impactSummary', { before: impact.data.sns_before, after: impact.data.sns_after })}</p>
                <CodeList title={t('cuf.impactAdded')} codes={impact.data.added} testId="cuf-impact-added" />
                <CodeList title={t('cuf.impactRemoved')} codes={impact.data.removed} testId="cuf-impact-removed" />
                <CodeList title={t('cuf.impactSubcategories')} codes={impact.data.subcategories_missing} testId="cuf-impact-subcategories" />
              </div>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              {t('actions.cancel')}
            </Button>
            <Button disabled={!impact.data || apply.isPending} onClick={() => apply.mutate()} data-testid="cuf-confirm-version">
              {t('cuf.confirmChange')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
