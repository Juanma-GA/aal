import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { ImportWizard } from '@/components/import/ImportWizard';
import { AttributeInput } from '@/components/reference/AttributeInput';
import { NewValueDialog } from '@/components/reference/NewValueDialog';
import { ConfirmDialog } from '@/components/settings/ConfirmDialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useReferenceTable, useReferenceValues, useRefreshReferenceTable, useUpdateReferenceValue } from '@/hooks/useReferenceTables';
import { useMe } from '@/hooks/useSession';
import { attributeText, cleanAttributes } from '@/lib/attributes';
import { saveFile } from '@/lib/download';
import { notifyError } from '@/lib/notify';
import { describeApiError } from '@/services/apiErrors';
import { exportReferenceTable, startReferenceImport } from '@/services/referenceApi';
import type { AttributeValue, ReferenceValue } from '@/types/reference';

type StateFilter = 'all' | 'active' | 'inactive';

interface Draft {
  description: string;
  definition: string;
  attributes: Record<string, AttributeValue | undefined>;
}

/** One reference table: its values with search and a state filter; for an
 *  admin, inline editing (optimistic, HR20), a new value, activating and
 *  deactivating with confirmation, and the Excel import. Export is for
 *  anyone. Attributes are shown by name (HR21). */
export function ReferenceTableView({ code, base }: { code: string; base: string }): React.JSX.Element {
  const { t } = useTranslation();
  const me = useMe();
  const table = useReferenceTable(code);
  const values = useReferenceValues(code);
  const refresh = useRefreshReferenceTable(code);
  const update = useUpdateReferenceValue(code);
  const [search, setSearch] = useState('');
  const [state, setState] = useState<StateFilter>('all');
  const [editing, setEditing] = useState<{ value: ReferenceValue; draft: Draft } | null>(null);
  const [toggling, setToggling] = useState<ReferenceValue | null>(null);
  const [creating, setCreating] = useState(false);
  const [importing, setImporting] = useState(false);
  const [exporting, setExporting] = useState(false);

  const rows = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase('es');
    return (values.data ?? []).filter(
      (v) =>
        (state === 'all' || v.is_active === (state === 'active')) &&
        (!needle || [v.code, v.description, v.definition ?? ''].some((text) => text.toLocaleLowerCase('es').includes(needle))),
    );
  }, [values.data, search, state]);

  if (table.isError) {
    return <p className="text-sm text-destructive" role="alert">{describeApiError(table.error, t).message}</p>;
  }
  if (!table.data || !values.data) return <Skeleton className="h-60 w-full" />;
  const info = table.data;
  const canEdit = Boolean(me.data?.is_admin) && info.editable;
  const showDefinition = values.data.some((v) => v.definition);
  const schema = info.attribute_schema;
  const columns = 3 + (showDefinition ? 1 : 0) + schema.length + (canEdit ? 1 : 0);

  const save = () => {
    if (!editing) return;
    const { value, draft } = editing;
    update.mutate({
      value,
      changes: { description: draft.description.trim(), definition: draft.definition.trim() || null, attributes: cleanAttributes(draft.attributes) },
    });
    setEditing(null);
  };
  const doExport = () => {
    setExporting(true);
    exportReferenceTable(code)
      .then(({ blob, fileName }) => saveFile(blob, fileName ?? `${code}.xlsx`))
      .catch((error: unknown) => notifyError(error, t))
      .finally(() => setExporting(false));
  };

  return (
    <div className="flex flex-col gap-4" data-testid={`reference-table-${code}`}>
      <div className="flex flex-col gap-1">
        <Link to={base} className="text-sm text-muted-foreground hover:underline">
          {t('reference.back')}
        </Link>
        <h3 className="text-xl font-semibold text-foreground">
          <span className="font-mono">{info.code}</span> · {info.name}
        </h3>
        <p className="text-sm text-muted-foreground">
          {t('reference.source')}: {info.source} · {t('reference.valuesCount', { active: info.active_count, total: info.value_count })}
        </p>
        {info.note ? (
          <p className="text-sm text-muted-foreground">
            {t('reference.note')}: {info.note}
          </p>
        ) : null}
        {canEdit ? null : <p className="text-sm text-muted-foreground" data-testid="reference-read-only">{t('reference.readOnly')}</p>}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Input className="w-full sm:w-80" placeholder={t('reference.search')} aria-label={t('reference.search')} value={search} onChange={(e) => setSearch(e.target.value)} data-testid="reference-search" />
        <Select value={state} onValueChange={(v) => setState(v as StateFilter)}>
          <SelectTrigger className="w-full sm:w-44" aria-label={t('reference.state')}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('reference.allStates')}</SelectItem>
            <SelectItem value="active">{t('reference.onlyActive')}</SelectItem>
            <SelectItem value="inactive">{t('reference.onlyInactive')}</SelectItem>
          </SelectContent>
        </Select>
        <div className="flex flex-wrap gap-2 sm:ml-auto">
          <Button variant="outline" onClick={doExport} disabled={exporting} data-testid="reference-export">
            {t('reference.export')}
          </Button>
          {canEdit ? (
            <>
              <Button variant="outline" onClick={() => setImporting(true)} data-testid="reference-import">
                {t('reference.import')}
              </Button>
              <Button onClick={() => setCreating(true)} data-testid="reference-new-value">
                {t('reference.newValue')}
              </Button>
            </>
          ) : null}
        </div>
      </div>

      <Table data-testid="reference-values">
        <TableHeader>
          <TableRow>
            <TableHead>{t('reference.code')}</TableHead>
            <TableHead>{t('reference.description')}</TableHead>
            {showDefinition ? <TableHead>{t('reference.definition')}</TableHead> : null}
            {schema.map((spec) => (
              <TableHead key={spec.key}>{spec.name}</TableHead>
            ))}
            <TableHead>{t('reference.state')}</TableHead>
            {canEdit ? (
              <TableHead>
                <span className="sr-only">{t('actions.more')}</span>
              </TableHead>
            ) : null}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={columns} className="text-muted-foreground">
                {t('reference.empty')}
              </TableCell>
            </TableRow>
          ) : (
            rows.map((v) => {
              const draft = editing?.value.id === v.id ? editing.draft : null;
              const setDraft = (patch: Partial<Draft>) => editing && setEditing({ ...editing, draft: { ...editing.draft, ...patch } });
              return (
                <TableRow key={v.id} data-testid={`value-row-${v.code}`} className={v.is_active ? undefined : 'text-muted-foreground'}>
                  <TableCell className="font-mono">{v.code}</TableCell>
                  <TableCell className="min-w-48 whitespace-normal">
                    {draft ? (
                      <Input aria-label={t('reference.description')} value={draft.description} onChange={(e) => setDraft({ description: e.target.value })} maxLength={1000} data-testid="edit-description" />
                    ) : (
                      v.description
                    )}
                  </TableCell>
                  {showDefinition ? (
                    <TableCell className="min-w-64 whitespace-normal">
                      {draft ? (
                        <Input aria-label={t('reference.definition')} value={draft.definition} onChange={(e) => setDraft({ definition: e.target.value })} maxLength={2000} />
                      ) : (
                        (v.definition ?? t('reference.none'))
                      )}
                    </TableCell>
                  ) : null}
                  {schema.map((spec) => (
                    <TableCell key={spec.key} className="whitespace-normal" data-testid={`attr-${spec.key}`}>
                      {draft ? (
                        <AttributeInput
                          id={`edit-${v.id}-${spec.key}`}
                          spec={spec}
                          value={draft.attributes[spec.key]}
                          onChange={(value) => setDraft({ attributes: { ...draft.attributes, [spec.key]: value } })}
                        />
                      ) : (
                        attributeText(spec, v.attributes[spec.key], t)
                      )}
                    </TableCell>
                  ))}
                  <TableCell>
                    <Badge variant={v.is_active ? 'secondary' : 'outline'} data-testid="value-state">
                      {v.is_active ? t('reference.active') : t('reference.inactive')}
                    </Badge>
                  </TableCell>
                  {canEdit ? (
                    <TableCell className="text-right whitespace-nowrap">
                      {draft ? (
                        <>
                          <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>
                            {t('actions.cancel')}
                          </Button>
                          <Button size="sm" onClick={save} disabled={!draft.description.trim()} data-testid="edit-save">
                            {t('actions.save')}
                          </Button>
                        </>
                      ) : (
                        <>
                          <Button
                            size="sm"
                            variant="ghost"
                            data-testid="edit-value"
                            onClick={() => setEditing({ value: v, draft: { description: v.description, definition: v.definition ?? '', attributes: { ...v.attributes } } })}
                          >
                            {t('actions.edit')}
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => setToggling(v)} data-testid="toggle-value">
                            {v.is_active ? t('reference.deactivate') : t('reference.activate')}
                          </Button>
                        </>
                      )}
                    </TableCell>
                  ) : null}
                </TableRow>
              );
            })
          )}
        </TableBody>
      </Table>

      <ConfirmDialog
        open={toggling !== null}
        onOpenChange={(open) => !open && setToggling(null)}
        title={toggling?.is_active ? t('reference.deactivateTitle', { code: toggling.code }) : t('reference.activateTitle', { code: toggling?.code ?? '' })}
        description={toggling?.is_active ? t('reference.deactivateHint') : t('reference.activateHint')}
        confirmLabel={toggling?.is_active ? t('reference.deactivate') : t('reference.activate')}
        onConfirm={() => {
          if (toggling) update.mutate({ value: toggling, changes: { is_active: !toggling.is_active } });
          setToggling(null);
        }}
      />
      {canEdit ? (
        <>
          <NewValueDialog table={info} open={creating} onOpenChange={setCreating} onCreated={refresh} />
          <ImportWizard
            open={importing}
            onOpenChange={setImporting}
            title={t('reference.importTitle', { table: info.code })}
            start={(file) => startReferenceImport(code, file)}
            onApplied={refresh}
          />
        </>
      ) : null}
    </div>
  );
}
