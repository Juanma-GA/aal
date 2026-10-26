import { Plus, Trash2 } from 'lucide-react';
import { Fragment, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArticleReferences } from '@/components/articles/ArticleReferences';
import { FieldHelp } from '@/components/articles/FieldHelp';
import { FieldInput } from '@/components/articles/FieldInput';
import { PageHeader } from '@/components/layout/PageHeader';
import { ConfirmDialog } from '@/components/settings/ConfirmDialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useArticle, useArticleHistory, useArticleRights, useDeleteArticle, useUpdateArticle } from '@/hooks/useArticles';
import { activeCodes, useFieldCodes } from '@/hooks/useFieldCodes';
import { useArticleFields } from '@/hooks/useReferenceTables';
import { FIELD_GROUPS, LIFE_CODE_FIELD, LIFE_QUANTITY_FIELD, NAME_FIELD, NOC_FIELD, cellProblem, cellValue, tableOf, type CellProblem } from '@/lib/articleFields';
import { cellProblemText, findingText } from '@/lib/articleText';
import { describeApiError } from '@/services/apiErrors';
import { ApiError } from '@/services/apiError';
import { NAME_ORIGINS, type Article, type ArticleChanges, type Finding, type LifeControl, type NameOrigin } from '@/types/articles';
import type { ArticleField } from '@/types/reference';

export const ARTICLES_PATH = '/articulos';

interface Draft {
  noc: string | null;
  nombre: string;
  origen_nombre: NameOrigin;
  fields: Record<string, string | null>;
  life: LifeControl[];
}

const draftOf = (a: Article): Draft => ({
  noc: a.noc, nombre: a.nombre, origen_nombre: a.origen_nombre, fields: { ...a.fields },
  life: a.life_controls.map((c) => ({ unit_code: c.unit_code, quantity: c.quantity })),
});

/** What the draft changes, as the API takes it. */
function changesOf(a: Article, d: Draft, defs: Record<string, ArticleField>): ArticleChanges {
  const out: ArticleChanges = {};
  for (const key of ['noc', 'nombre', 'origen_nombre'] as const) {
    if ((d[key] ?? null) !== (a[key] ?? null)) Object.assign(out, { [key]: d[key] });
  }
  const fields: Record<string, string | null> = {};
  for (const [prisma, value] of Object.entries(d.fields)) {
    const def = defs[prisma];
    const sent = def ? cellValue(def, value) : value;
    if (sent !== (a.fields[prisma] ?? null)) fields[prisma] = sent;
  }
  if (Object.keys(fields).length) out.fields = fields;
  const life = d.life.filter((c) => c.unit_code || c.quantity);
  const stored = a.life_controls.map((c) => ({ unit_code: c.unit_code, quantity: c.quantity }));
  if (JSON.stringify(life) !== JSON.stringify(stored)) out.life_controls = life.map((c) => ({ unit_code: c.unit_code, quantity: c.quantity ? c.quantity.replace(',', '.') : null }));
  return out;
}

function FieldLabel({ field, htmlFor }: { field: ArticleField; htmlFor: string }): React.JSX.Element {
  const { t } = useTranslation();
  return (
    <div className="flex items-start justify-between gap-2">
      <Label htmlFor={htmlFor} className="leading-snug">
        {field.name}
        <span className="ml-1 font-normal text-muted-foreground">
          {field.guide_field === 'N/A' ? t('articles.noMar06') : t('articles.mar06', { number: field.guide_field })} · <span className="font-mono text-xs">{field.prisma_code}</span>
        </span>
      </Label>
      <FieldHelp field={field} />
    </div>
  );
}

/** An article (E12): its 30 fields in groups, each with its MAR06 number,
 *  PRISMA code and help; its references (P/N + NCAGE, E13); its AR findings (each takes you to its field),
 *  where it is used and its history. Editing needs articulos.editar. */
export function ArticlePage(): React.JSX.Element {
  const { t, i18n } = useTranslation();
  const { articleId = '' } = useParams();
  const navigate = useNavigate();
  const article = useArticle(articleId);
  const fieldList = useArticleFields();
  const rights = useArticleRights();
  const codes = useFieldCodes(fieldList.data);
  const history = useArticleHistory(articleId);
  const update = useUpdateArticle(articleId);
  const remove = useDeleteArticle();
  // The draft belongs to one version of the article: a new one from the
  // server (saved, or reloaded) starts it again.
  const [edit, setEdit] = useState<{ key: string; draft: Draft } | null>(null);
  const [deleting, setDeleting] = useState(false);
  const defs = useMemo(() => Object.fromEntries((fieldList.data ?? []).map((f) => [f.prisma_code, f])), [fieldList.data]);
  const names = useMemo(() => Object.fromEntries((fieldList.data ?? []).map((f) => [f.prisma_code, f.name])), [fieldList.data]);
  const maxLifeControls = rights.data?.max_life_controls ?? 0;
  const canEdit = Boolean(rights.data?.can_edit);

  const versionKey = article.data ? `${article.data.id}:${article.data.version}` : '';
  const draft = article.data ? (edit?.key === versionKey ? edit.draft : draftOf(article.data)) : null;
  const setDraft = (next: Draft) => setEdit({ key: versionKey, draft: next });

  const title = article.data?.nombre ?? t('articles.title');
  const header = <PageHeader crumbs={[{ label: t('articles.title'), to: ARTICLES_PATH }, { label: title }]} title={title} />;
  if (article.isError) {
    return (
      <div className="flex flex-col gap-6">
        {header}
        <p className="text-sm text-destructive" role="alert" data-testid="article-error">
          {describeApiError(article.error, t).message}
        </p>
      </div>
    );
  }
  if (!article.data || !fieldList.data || !draft) return <div className="flex flex-col gap-6">{header}<Skeleton className="h-96 w-full" /></div>;
  const a = article.data;
  const changes = changesOf(a, draft, defs);
  const dirty = Object.keys(changes).length > 0;
  const serverProblems = update.error instanceof ApiError && update.error.detail.code === 'article_invalid'
    ? (update.error.detail.problems as { field: string; code: string; params: Record<string, string | number> }[])
    : [];
  const problemOf = (prisma: string, value: string | null, stored: string | null | undefined): CellProblem => {
    const def = defs[prisma];
    if (!def) return null;
    const table = tableOf(def);
    return cellProblem(def, value, table ? activeCodes(codes[table]) : undefined, stored);
  };
  const fieldProblems = Object.entries(draft.fields).map(([p, v]) => [p, problemOf(p, v, a.fields[p])] as const).filter(([, p]) => p);
  const lifeProblems = draft.life.flatMap((c, i) => [
    problemOf(LIFE_CODE_FIELD, c.unit_code, a.life_controls[i]?.unit_code),
    problemOf(LIFE_QUANTITY_FIELD, c.quantity, null),
  ]).filter(Boolean);
  const nameMissing = !draft.nombre.trim();
  const blocked = fieldProblems.length > 0 || lifeProblems.length > 0 || nameMissing;
  const set = (patch: Partial<Draft>) => setDraft({ ...draft, ...patch });
  const setField = (prisma: string, value: string | null) => set({ fields: { ...draft.fields, [prisma]: value } });
  const goTo = (f: Finding) => {
    const el = document.getElementById(`field-${f.field}`);
    el?.scrollIntoView({ block: 'center' });
    el?.focus();
  };
  const when = (iso: string) => new Intl.DateTimeFormat(i18n.language, { dateStyle: 'short', timeStyle: 'short' }).format(new Date(iso));
  const disabled = !canEdit || update.isPending;

  const plainField = (prisma: string) => {
    const def = defs[prisma];
    if (!def) return null;
    const problem = problemOf(prisma, draft.fields[prisma] ?? null, a.fields[prisma]) ?? serverProblems.find((p) => p.field === prisma) ?? null;
    return (
      <div key={prisma} className="flex flex-col gap-1">
        <FieldLabel field={def} htmlFor={`field-${prisma}`} />
        <FieldInput
          id={`field-${prisma}`}
          field={def}
          value={draft.fields[prisma] ?? null}
          onChange={(v) => setField(prisma, v)}
          values={tableOf(def) ? codes[tableOf(def) ?? ''] : undefined}
          disabled={disabled}
          invalid={Boolean(problem)}
        />
        {problem ? <p className="text-xs text-destructive">{cellProblemText(t, problem)}</p> : null}
      </div>
    );
  };

  const identity = (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {[NOC_FIELD, NAME_FIELD].map((prisma) => {
        const def = defs[prisma];
        const key = prisma === NOC_FIELD ? 'noc' : 'nombre';
        const problem = serverProblems.find((p) => p.field === key);
        return def ? (
          <div key={prisma} className="flex flex-col gap-1">
            <FieldLabel field={def} htmlFor={`field-${prisma}`} />
            <Input
              id={`field-${prisma}`}
              data-testid={`field-${prisma}`}
              className={prisma === NOC_FIELD ? 'font-mono' : undefined}
              value={(key === 'noc' ? draft.noc : draft.nombre) ?? ''}
              onChange={(e) => set(key === 'noc' ? { noc: e.target.value || null } : { nombre: e.target.value })}
              disabled={disabled}
              aria-invalid={Boolean(problem) || (key === 'nombre' && nameMissing) || undefined}
            />
            {problem ? <p className="text-xs text-destructive">{cellProblemText(t, problem)}</p> : null}
          </div>
        ) : null;
      })}
      <div className="flex flex-col gap-1">
        <Label htmlFor="field-origen">{t('articles.identity.origen_nombre')}</Label>
        <Select value={draft.origen_nombre} onValueChange={(v) => set({ origen_nombre: v as NameOrigin })} disabled={disabled}>
          <SelectTrigger id="field-origen" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {NAME_ORIGINS.map((o) => (
              <SelectItem key={o} value={o}>
                {t(`articles.origins.${o}`)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );

  const lifeEditor = (
    <div className="flex flex-col gap-2 sm:col-span-2" data-testid="life-controls">
      <div className="flex flex-wrap items-center gap-2">
        {[LIFE_CODE_FIELD, LIFE_QUANTITY_FIELD].map((p) => (defs[p] ? <FieldLabel key={p} field={defs[p]} htmlFor={p === LIFE_CODE_FIELD ? 'field-cdUniVidaA' : 'field-caVidaArt'} /> : null))}
      </div>
      {draft.life.length === 0 ? <p className="text-sm text-muted-foreground">{t('articles.noLifeControl')}</p> : null}
      {draft.life.map((c, i) => (
        <div key={i} className="grid grid-cols-[1fr_8rem_auto] items-center gap-2">
          <FieldInput
            id={i === 0 ? 'field-cdUniVidaA' : `field-cdUniVidaA-${i + 1}`}
            field={defs[LIFE_CODE_FIELD]}
            value={c.unit_code}
            values={codes.D114}
            onChange={(v) => set({ life: draft.life.map((x, j) => (j === i ? { ...x, unit_code: v } : x)) })}
            disabled={disabled}
          />
          <Input
            id={i === 0 ? 'field-caVidaArt' : `field-caVidaArt-${i + 1}`}
            data-testid={i === 0 ? 'field-caVidaArt' : `field-caVidaArt-${i + 1}`}
            aria-label={t('articles.lifeQuantity', { position: i + 1 })}
            className="text-right font-mono"
            inputMode="decimal"
            value={c.quantity ?? ''}
            onChange={(e) => set({ life: draft.life.map((x, j) => (j === i ? { ...x, quantity: e.target.value || null } : x)) })}
            disabled={disabled}
          />
          <Button variant="ghost" size="icon" aria-label={t('articles.removeLifeControl', { position: i + 1 })} disabled={disabled} onClick={() => set({ life: draft.life.filter((_x, j) => j !== i) })}>
            <Trash2 aria-hidden="true" />
          </Button>
        </div>
      ))}
      {canEdit && draft.life.length < maxLifeControls ? (
        <Button variant="outline" size="sm" className="self-start" onClick={() => set({ life: [...draft.life, { unit_code: null, quantity: null }] })} data-testid="add-life-control">
          <Plus aria-hidden="true" />
          {t('articles.addLifeControl')}
        </Button>
      ) : null}
    </div>
  );

  return (
    <div className="flex flex-col gap-6" data-testid="article-page">
      {header}
      <div className="flex flex-wrap items-center gap-2">
        {a.noc ? <Badge variant="secondary" className="font-mono">{a.noc}</Badge> : <Badge variant="outline" className="border-warning text-warning">{t('articles.provisional')}</Badge>}
        {a.finding_codes.map((code) => (
          <Badge key={code} variant="outline" data-testid={`article-badge-${code}`}>
            {code}
          </Badge>
        ))}
        {canEdit ? (
          <div className="flex gap-2 sm:ml-auto">
            <Button variant="outline" disabled={!dirty || update.isPending} onClick={() => setDraft(draftOf(a))}>
              {t('articles.discardChanges')}
            </Button>
            <Button disabled={!dirty || blocked || update.isPending} onClick={() => update.mutate({ article: a, changes })} data-testid="article-save">
              {t('actions.save')}
            </Button>
            <Button variant="ghost" className="text-destructive" onClick={() => setDeleting(true)} data-testid="article-delete">
              <Trash2 aria-hidden="true" />
              {t('articles.delete')}
            </Button>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground sm:ml-auto">{t('articles.readOnly')}</p>
        )}
      </div>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="flex flex-col gap-6">
          {FIELD_GROUPS.map((group) => (
            <Fragment key={group.key}>
            <Card data-testid={`article-group-${group.key}`}>
              <CardHeader>
                <CardTitle>{t(`articles.groups.${group.key}`)}</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {group.key === 'identification' ? <div className="sm:col-span-2">{identity}</div> : null}
                {group.fields.filter((p) => p !== NOC_FIELD && p !== NAME_FIELD && p !== LIFE_CODE_FIELD && p !== LIFE_QUANTITY_FIELD).map(plainField)}
                {group.fields.includes(LIFE_CODE_FIELD) ? lifeEditor : null}
              </CardContent>
            </Card>
            {group.key === 'identification' ? <ArticleReferences article={a} canEdit={canEdit} /> : null}
            </Fragment>
          ))}
        </div>
        <div className="flex flex-col gap-6">
          <Card data-testid="article-findings">
            <CardHeader>
              <CardTitle>{t('articles.findingsTitle')}</CardTitle>
              <CardDescription>{t('articles.findingsHint')}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3 text-sm">
              {a.findings.length === 0 ? <p className="text-muted-foreground" data-testid="article-no-findings">{t('articles.noFindings')}</p> : null}
              {a.findings.map((f, i) => (
                <div key={`${f.code}-${f.field}-${i}`} className="flex flex-col gap-1" data-testid={`finding-${f.code}`}>
                  <div className="flex items-center gap-2">
                    <Badge variant={f.severity === 'bloqueante' ? 'destructive' : 'outline'}>{f.code}</Badge>
                    <span className="font-medium">{t(`articles.rules.${f.code}.title`)}</span>
                  </div>
                  <p>{findingText(t, f, names)}</p>
                  <button type="button" className="self-start text-link underline-offset-2 hover:underline" onClick={() => goTo(f)} data-testid={`finding-go-${f.code}`}>
                    {t('articles.goToField', { field: defs[f.field]?.name ?? f.field })}
                  </button>
                </div>
              ))}
            </CardContent>
          </Card>
          <Card data-testid="article-where-used">
            <CardHeader>
              <CardTitle>{t('articles.whereUsed')}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm">
              {a.where_used.length === 0 ? <p className="text-muted-foreground">{t('articles.notUsed')}</p> : null}
              <ul className="flex flex-col gap-1">
                {a.where_used.map((u, i) => (
                  <li key={`${u.kind}-${i}`}>
                    {u.kind === 'material_cuf' && u.material_id ? (
                      <>
                        {t('articles.usage.material_cuf')}{' '}
                        <Link to={`/materiales/${u.material_id}/ficha`} className="text-link underline-offset-2 hover:underline">
                          {u.material_name}
                        </Link>
                      </>
                    ) : (
                      t(`articles.usage.${u.kind}`, { defaultValue: u.kind })
                    )}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
          <Card data-testid="article-history">
            <CardHeader>
              <CardTitle>{t('articles.history')}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm">
              <ul className="flex flex-col gap-2">
                {(history.data ?? []).map((h) => (
                  <li key={h.id}>
                    <span className="font-medium">{t(`audit.actions.${h.action}`)}</span>
                    <span className="block text-xs text-muted-foreground">
                      {when(h.at)} · {h.user ?? t('articles.byScript')}
                    </span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>
      </div>
      <ConfirmDialog
        open={deleting}
        onOpenChange={setDeleting}
        title={t('articles.deleteTitle', { name: a.nombre })}
        description={t('articles.deleteHint')}
        confirmLabel={t('articles.delete')}
        onConfirm={() => remove.mutate(a, { onSuccess: () => navigate(ARTICLES_PATH) })}
      />
    </div>
  );
}
