// Configuración funcional física (E13, RF-02): the CONFUNFIS of the
// material in three views -- the physical tree by CS, the functional view
// over its normalized configuration, the Anexo XI table -- and the card of
// a row in a side panel. The tab and the open row live in the URL (?tab,
// ?fila), nothing in the browser (HR1). Editing needs confunfis.editar.
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { BookImportDialog } from '@/components/confunfis/BookImportDialog';
import { CufPartsTable } from '@/components/confunfis/CufPartsTable';
import { FunctionalView } from '@/components/confunfis/FunctionalView';
import { PhysicalTree } from '@/components/confunfis/PhysicalTree';
import { ProductsTable } from '@/components/confunfis/ProductsTable';
import { RowFormDialog } from '@/components/confunfis/RowFormDialog';
import { RowSheet } from '@/components/confunfis/RowSheet';
import { RowsTable } from '@/components/confunfis/RowsTable';
import { PageHeader } from '@/components/layout/PageHeader';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { confunfisKey, useAlternativeCs, useConfunfisSummary } from '@/hooks/useConfunfis';
import { useMaterialOfPage } from '@/hooks/useMaterialOfPage';
import { useMe } from '@/hooks/useSession';
import { saveFile } from '@/lib/download';
import { notifyError } from '@/lib/notify';
import { describeApiError } from '@/services/apiErrors';
import { exportBook } from '@/services/confunfisBookApi';
import type { BookExport } from '@/types/confunfisBook';
import { positionOf, type PositionRow } from '@/types/confunfis';

const EXPORTS: BookExport[] = ['anexo', 'aal', 'plantilla'];
const TABS = ['arbol', 'funcional', 'tabla', 'partes', 'productos'] as const;
type Tab = (typeof TABS)[number];

function AlternativeCsDialog({ materialId, row, onClose, onDone }: { materialId: string; row: PositionRow; onClose: () => void; onDone: (id: string) => void }): React.JSX.Element {
  const { t } = useTranslation();
  const mutation = useAlternativeCs(materialId);
  const [cs, setCs] = useState('');
  const parts = cs.trim().toUpperCase().split(/\s+/);
  const valid = parts.length === 3 && /^[A-Z0-9]{6}$/.test(parts[0]) && /^\d{2}$/.test(parts[1]) && /^\d{2}$/.test(parts[2]);
  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent data-testid="alternative-cs-dialog">
        <DialogHeader>
          <DialogTitle>{t('confunfis.alternativeCs.title', { position: positionOf(row) })}</DialogTitle>
          <DialogDescription>{t('confunfis.alternativeCs.hint')}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1">
          <Label htmlFor="alt-cs">{t('confunfis.fields.cs')}</Label>
          <Input id="alt-cs" className="font-mono" placeholder={t('confunfis.alternativeCs.placeholder')} value={cs} onChange={(e) => setCs(e.target.value)} data-testid="alternative-cs-input" />
          {mutation.error ? <p className="text-sm text-destructive" role="alert">{describeApiError(mutation.error, t).message}</p> : null}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{t('actions.cancel')}</Button>
          <Button
            disabled={!valid || mutation.isPending}
            onClick={() => mutation.mutate({ row, cs: { cs_sns: parts[0], cs_co: parts[1], cs_al: parts[2] } }, { onSuccess: (created) => onDone(created.id) })}
            data-testid="alternative-cs-save"
          >
            {t('actions.save')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ConfunfisPage(): React.JSX.Element {
  const { t } = useTranslation();
  const material = useMaterialOfPage();
  const summary = useConfunfisSummary(material.id);
  const [params] = useSearchParams();
  const navigate = useNavigate();
  // The tab is the path's (…/confunfis/partes: the module's own route, E14) or, as before, ?tab.
  const { tab: pathTab } = useParams();
  const tab: Tab = TABS.find((x) => x === (pathTab ?? params.get('tab'))) ?? 'arbol';
  const rowId = params.get('fila');
  const canEdit = material.permissions.includes('confunfis.editar');
  const [form, setForm] = useState<{ row: PositionRow | null } | null>(null);
  const [altCs, setAltCs] = useState<PositionRow | null>(null);
  const [importing, setImporting] = useState<'anexo' | 'aal' | null>(null);
  const me = useMe();
  const queryClient = useQueryClient();
  const title = t('confunfis.title');
  const doExport = (kind: BookExport) => {
    exportBook(material.id, kind)
      .then(({ blob, fileName }) => saveFile(blob, fileName ?? 'CONFUNFIS.xlsx'))
      .catch((error: unknown) => notifyError(error, t));
  };

  const go = (next: { tab?: Tab; fila?: string | null }) => {
    const out = new URLSearchParams(params);
    out.delete('tab');
    if (next.fila !== undefined) {
      if (next.fila) out.set('fila', next.fila);
      else out.delete('fila');
    }
    const target = next.tab ?? tab;
    const path = `/materiales/${material.id}/confunfis${target === 'arbol' ? '' : `/${target}`}`;
    const query = out.toString();
    navigate(`${path}${query ? `?${query}` : ''}`);
  };
  // Clicking the open row again closes its card (E15: the panel is docked, the list stays clickable).
  const open = (row: PositionRow) => go({ fila: row.id === rowId ? null : row.id });

  return (
    <div className="flex flex-col gap-6" data-testid="confunfis-page">
      <PageHeader crumbs={[{ label: material.name, to: `/materiales/${material.id}` }, { label: title }]} title={title} />
      <div className="flex flex-wrap items-center gap-2">
        {summary.data ? (
          <>
            <Badge data-testid="confunfis-summary-rows">{t('confunfis.summary.rows', { count: summary.data.rows })}</Badge>
            <Badge variant="secondary">{t('confunfis.summary.positions', { count: summary.data.positions })}</Badge>
            <Badge variant="secondary">{t('confunfis.summary.covered', { covered: summary.data.sns_covered, total: summary.data.sns_in_config })}</Badge>
            {summary.data.multifunction_rows ? <Badge variant="outline">{t('confunfis.summary.multifunction', { count: summary.data.multifunction_rows })}</Badge> : null}
            {summary.data.incompatibility_rows ? <Badge variant="outline">{t('confunfis.summary.incompatible', { count: summary.data.incompatibility_rows })}</Badge> : null}
            {summary.data.with_observations ? (
              <Badge variant="warning">{t('confunfis.summary.observations', { count: summary.data.with_observations })}</Badge>
            ) : null}
          </>
        ) : null}
        <div className="flex flex-wrap items-center gap-2 sm:ml-auto">
          {canEdit ? null : <p className="text-sm text-muted-foreground">{t('confunfis.readOnly')}</p>}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" data-testid="confunfis-export">{t('confunfisBook.export')}</Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {EXPORTS.map((kind) => (
                <DropdownMenuItem key={kind} onSelect={() => doExport(kind)} data-testid={`confunfis-export-${kind}`}>
                  {t(`confunfisBook.exports.${kind}`)}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          {canEdit ? (
            <>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" data-testid="confunfis-import">{t('confunfisBook.import')}</Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {(['anexo', 'aal'] as const).map((book) => (
                    <DropdownMenuItem key={book} onSelect={() => setImporting(book)} data-testid={`confunfis-import-${book}`}>
                      {t(`confunfisBook.exports.${book}`)}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
              <Button onClick={() => setForm({ row: null })} data-testid="confunfis-new-row">{t('confunfis.newRow')}</Button>
            </>
          ) : null}
        </div>
      </div>
      <p className="text-sm text-muted-foreground">{t('confunfis.hint')}</p>
      <Tabs value={tab} onValueChange={(v) => go({ tab: v as Tab })}>
        <TabsList className="flex-wrap">
          {TABS.map((name) => (
            <TabsTrigger key={name} value={name} data-testid={`confunfis-tab-${name}`}>
              {t(`confunfis.tabs.${name}`)}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value="arbol">
          <PhysicalTree materialId={material.id} selected={rowId} onSelect={open} />
        </TabsContent>
        <TabsContent value="funcional">
          <FunctionalView materialId={material.id} onSelect={open} />
        </TabsContent>
        <TabsContent value="tabla">
          <RowsTable materialId={material.id} onSelect={open} />
        </TabsContent>
        <TabsContent value="partes">
          <CufPartsTable materialId={material.id} />
        </TabsContent>
        <TabsContent value="productos">
          <ProductsTable materialId={material.id} canEdit={canEdit} />
        </TabsContent>
      </Tabs>
      {rowId ? (
        <RowSheet
          materialId={material.id} rowId={rowId} canEdit={canEdit}
          onOpen={(id) => go({ fila: id })} onEdit={(row) => setForm({ row })} onAlternativeCs={setAltCs}
        />
      ) : null}
      {form ? (
        <RowFormDialog materialId={material.id} row={form.row} onClose={() => setForm(null)} onSaved={(saved) => { setForm(null); go({ fila: saved.id }); }} />
      ) : null}
      <BookImportDialog
        materialId={material.id} materialName={material.name} book={importing ?? 'anexo'} isAdmin={Boolean(me.data?.is_admin)}
        open={importing !== null} onOpenChange={(next) => { if (!next) setImporting(null); }}
        onApplied={() => {
          void queryClient.invalidateQueries({ queryKey: confunfisKey(material.id) });
          void queryClient.invalidateQueries({ queryKey: ['articles'] });
        }}
      />
      {altCs ? (
        <AlternativeCsDialog materialId={material.id} row={altCs} onClose={() => setAltCs(null)} onDone={(id) => { setAltCs(null); go({ fila: id }); }} />
      ) : null}
    </div>
  );
}
