import { Check, Pencil, Plus, Star, Trash2, X } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ConfirmDialog } from '@/components/settings/ConfirmDialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useReferenceMutation } from '@/hooks/useArticles';
import type { Article, ArticleReference } from '@/types/articles';

const clean = (value: string): string | null => value.trim().toUpperCase() || null;

/** The article's references (E13, NT §9.1.6): one NOC, several P/N +
 *  NCAGE. The principal one is "the" P/N of the list and of the Fichero
 *  Carga world; any other can become it. Adding, editing and removing are
 *  optimistic (HR20); removing asks first (HR9: it is kept, as removed). */
export function ArticleReferences({ article, canEdit }: { article: Article; canEdit: boolean }): React.JSX.Element {
  const { t } = useTranslation();
  const mutation = useReferenceMutation(article.id);
  const [pn, setPn] = useState('');
  const [ncage, setNcage] = useState('');
  const [editing, setEditing] = useState<{ id: string; pn: string; ncage: string } | null>(null);
  const [removing, setRemoving] = useState<ArticleReference | null>(null);
  const pending = (r: ArticleReference) => r.id.startsWith('pending-');

  const add = () => {
    const value = pn.trim();
    if (!value) return;
    mutation.mutate({ kind: 'add', pn: value, ncage: clean(ncage) }, { onSuccess: () => { setPn(''); setNcage(''); } });
  };
  const save = (r: ArticleReference) => {
    if (!editing) return;
    const changes = { pn: editing.pn.trim(), ncage: clean(editing.ncage) };
    if (changes.pn && (changes.pn !== r.pn || changes.ncage !== r.ncage)) mutation.mutate({ kind: 'update', reference: r, changes });
    setEditing(null);
  };

  return (
    <Card data-testid="article-references">
      <CardHeader>
        <CardTitle>{t('articles.references.title')}</CardTitle>
        <CardDescription>{t('articles.references.hint')}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {article.references.length === 0 ? <p className="text-sm text-muted-foreground" data-testid="references-none">{t('articles.references.none')}</p> : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('articles.identity.pn')}</TableHead>
                <TableHead className="w-28">{t('articles.identity.ncage')}</TableHead>
                <TableHead className="w-32">{t('articles.references.origin')}</TableHead>
                <TableHead className="w-36">
                  <span className="sr-only">{t('articles.references.actions')}</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {article.references.map((r) => (
                <TableRow key={r.id} data-testid={`reference-${r.pn}`}>
                  {editing?.id === r.id ? (
                    <>
                      <TableCell>
                        <Input aria-label={t('articles.identity.pn')} className="font-mono" value={editing.pn} onChange={(e) => setEditing({ ...editing, pn: e.target.value })} />
                      </TableCell>
                      <TableCell>
                        <Input aria-label={t('articles.identity.ncage')} className="font-mono" value={editing.ncage} onChange={(e) => setEditing({ ...editing, ncage: e.target.value })} />
                      </TableCell>
                      <TableCell />
                      <TableCell className="text-right">
                        <Button variant="ghost" size="icon" aria-label={t('actions.save')} onClick={() => save(r)} data-testid="reference-save">
                          <Check aria-hidden="true" />
                        </Button>
                        <Button variant="ghost" size="icon" aria-label={t('actions.cancel')} onClick={() => setEditing(null)}>
                          <X aria-hidden="true" />
                        </Button>
                      </TableCell>
                    </>
                  ) : (
                    <>
                      <TableCell className="font-mono">
                        {r.pn}
                        {r.principal ? <Badge variant="secondary" className="ml-2 font-sans">{t('articles.references.principal')}</Badge> : null}
                      </TableCell>
                      <TableCell className="font-mono">{r.ncage ?? t('reference.none')}</TableCell>
                      <TableCell>{t(`articles.references.origins.${r.origin}`)}</TableCell>
                      <TableCell className="text-right">
                        {canEdit ? (
                          <>
                            {!r.principal ? (
                              <Button
                                variant="ghost" size="icon" disabled={pending(r)} aria-label={t('articles.references.makePrincipal', { pn: r.pn })}
                                onClick={() => mutation.mutate({ kind: 'update', reference: r, changes: { principal: true } })} data-testid="reference-make-principal"
                              >
                                <Star aria-hidden="true" />
                              </Button>
                            ) : null}
                            <Button variant="ghost" size="icon" disabled={pending(r)} aria-label={t('articles.references.edit', { pn: r.pn })} onClick={() => setEditing({ id: r.id, pn: r.pn, ncage: r.ncage ?? '' })}>
                              <Pencil aria-hidden="true" />
                            </Button>
                            <Button variant="ghost" size="icon" className="text-destructive" disabled={pending(r)} aria-label={t('articles.references.remove', { pn: r.pn })} onClick={() => setRemoving(r)}>
                              <Trash2 aria-hidden="true" />
                            </Button>
                          </>
                        ) : null}
                      </TableCell>
                    </>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {canEdit ? (
          <form className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_8rem_auto]" onSubmit={(e) => { e.preventDefault(); add(); }}>
            <Input aria-label={t('articles.references.newPn')} placeholder={t('articles.identity.pn')} className="font-mono" value={pn} onChange={(e) => setPn(e.target.value)} data-testid="reference-new-pn" />
            <Input aria-label={t('articles.references.newNcage')} placeholder={t('articles.identity.ncage')} className="font-mono" value={ncage} onChange={(e) => setNcage(e.target.value)} data-testid="reference-new-ncage" />
            <Button type="submit" variant="outline" disabled={!pn.trim()} data-testid="reference-add">
              <Plus aria-hidden="true" />
              {t('articles.references.add')}
            </Button>
          </form>
        ) : null}
      </CardContent>
      <ConfirmDialog
        open={removing !== null}
        onOpenChange={(open) => { if (!open) setRemoving(null); }}
        title={t('articles.references.removeTitle', { pn: removing?.pn ?? '' })}
        description={removing?.principal ? t('articles.references.removePrincipalHint') : t('articles.references.removeHint')}
        confirmLabel={t('articles.references.removeConfirm')}
        onConfirm={() => { if (removing) mutation.mutate({ kind: 'remove', reference: removing }); setRemoving(null); }}
      />
    </Card>
  );
}
