import { type InfiniteData, type QueryClient, type QueryKey, useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { notifyError } from '@/lib/notify';
import {
  addReference,
  createArticle,
  deleteArticle,
  fetchArticle,
  fetchArticleHistory,
  fetchArticleRights,
  fetchArticles,
  fetchLatestRevalidation,
  removeReference,
  saveArticleBatch,
  startRevalidation,
  updateArticle,
  updateReference,
} from '@/services/articlesApi';
import type { Article, ArticleChanges, ArticleFilters, ArticlePage, ArticleReference, ArticleRow, BatchResult, ReferenceChanges } from '@/types/articles';

export const articlesKey = ['articles'] as const;
export const articleKey = (id: string) => ['articles', 'one', id] as const;

export function useArticleRights() {
  return useQuery({ queryKey: ['articles', 'rights'], queryFn: fetchArticleRights });
}

/** The list, page by page as it scrolls (the view is virtualized). */
export function useArticleList(filters: ArticleFilters) {
  return useInfiniteQuery({
    queryKey: ['articles', 'list', filters],
    queryFn: ({ pageParam }) => fetchArticles(filters, pageParam),
    initialPageParam: 1,
    getNextPageParam: (last) => (last.page * last.page_size < last.total ? last.page + 1 : undefined),
  });
}

export function useArticle(id: string) {
  return useQuery({ queryKey: articleKey(id), queryFn: () => fetchArticle(id) });
}

export function useArticleHistory(id: string) {
  return useQuery({ queryKey: ['articles', 'one', id, 'history'], queryFn: () => fetchArticleHistory(id) });
}

/** Saving the card: shown at once on the cached article, saved in the
 *  background, undone if the server refuses it (HR20; a 409 offers to
 *  reload). The server's answer (findings, version) replaces it. */
export function useUpdateArticle(id: string) {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: ({ article, changes }: { article: Article; changes: ArticleChanges }) => updateArticle(id, article.version, changes),
    onMutate: async ({ article, changes }) => {
      await queryClient.cancelQueries({ queryKey: articleKey(id) });
      const previous = queryClient.getQueryData<Article>(articleKey(id));
      queryClient.setQueryData<Article>(articleKey(id), {
        ...article,
        ...changes,
        fields: { ...article.fields, ...changes.fields },
        life_controls: changes.life_controls ?? article.life_controls,
      } as Article);
      return { previous };
    },
    onError: (error, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(articleKey(id), context.previous);
      notifyError(error, t, () => void queryClient.invalidateQueries({ queryKey: articleKey(id) }));
    },
    onSuccess: (saved) => {
      queryClient.setQueryData(articleKey(id), saved);
      void queryClient.invalidateQueries({ queryKey: ['articles', 'list'] });
      void queryClient.invalidateQueries({ queryKey: ['articles', 'one', id, 'history'] });
    },
  });
}

/** A new article is not optimistic: its id comes from the server. */
export function useCreateArticle() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createArticle,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['articles', 'list'] }),
  });
}

type ListData = InfiniteData<ArticlePage, number>;

/** Every cached page of the list, changed row by row. */
function mapListRows(queryClient: QueryClient, fn: (row: ArticleRow) => ArticleRow | null): [QueryKey, ListData | undefined][] {
  const previous = queryClient.getQueriesData<ListData>({ queryKey: ['articles', 'list'] });
  for (const [key, data] of previous) {
    if (!data) continue;
    queryClient.setQueryData<ListData>(key, {
      ...data,
      pages: data.pages.map((p) => ({ ...p, items: p.items.map(fn).filter((r): r is ArticleRow => r !== null) })),
    });
  }
  return previous;
}

function restore(queryClient: QueryClient, previous: [QueryKey, ListData | undefined][] | undefined): void {
  for (const [key, data] of previous ?? []) queryClient.setQueryData(key, data);
}

/** Deleting: the row leaves the list at once (HR20), back if the server
 *  refuses it. */
export function useDeleteArticle() {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (article: ArticleRow) => deleteArticle(article.id, article.version),
    onMutate: async (article) => {
      await queryClient.cancelQueries({ queryKey: ['articles', 'list'] });
      return { previous: mapListRows(queryClient, (r) => (r.id === article.id ? null : r)) };
    },
    onError: (error, _article, context) => {
      restore(queryClient, context?.previous);
      notifyError(error, t);
    },
    onSettled: () => void queryClient.invalidateQueries({ queryKey: ['articles', 'list'] }),
  });
}

type BatchItem = { id: string; version: number; fields: Record<string, string | null> };

/** The grid's save: the new values show on the list at once (HR20); each
 *  row saved takes the server's answer (version, findings), each refused
 *  one goes back to what is stored. */
export function useSaveBatch() {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (items: BatchItem[]) => saveArticleBatch(items),
    onMutate: async (items) => {
      await queryClient.cancelQueries({ queryKey: ['articles', 'list'] });
      const byId = new Map(items.map((i) => [i.id, i]));
      return { previous: mapListRows(queryClient, (r) => (byId.has(r.id) ? { ...r, fields: { ...r.fields, ...byId.get(r.id)?.fields } } : r)) };
    },
    onError: (error, _items, context) => {
      restore(queryClient, context?.previous);
      notifyError(error, t);
    },
    onSuccess: (results: BatchResult[], _items, context) => {
      const saved = new Map(results.filter((r) => r.ok && r.article).map((r) => [r.id, r.article as ArticleRow]));
      const refused = new Set(results.filter((r) => !r.ok).map((r) => r.id));
      const before = new Map((context?.previous ?? []).flatMap(([, data]) => data?.pages.flatMap((p) => p.items) ?? []).map((r) => [r.id, r]));
      mapListRows(queryClient, (r) => saved.get(r.id) ?? (refused.has(r.id) ? (before.get(r.id) ?? r) : r));
      // A refused row: its stored data (and version) may have changed.
      if (refused.size) void queryClient.invalidateQueries({ queryKey: ['articles', 'list'] });
    },
  });
}

export type ReferenceAction =
  | { kind: 'add'; pn: string; ncage: string | null }
  | { kind: 'update'; reference: ArticleReference; changes: ReferenceChanges }
  | { kind: 'remove'; reference: ArticleReference };

/** The references as they will be once the server agrees (principal first). */
function referencesAfter(refs: ArticleReference[], action: ReferenceAction): ArticleReference[] {
  if (action.kind === 'add') {
    const now = new Date().toISOString();
    const added: ArticleReference = {
      id: `pending-${now}`, pn: action.pn, ncage: action.ncage, principal: refs.length === 0, origin: 'manual', version: 0, created_at: now, updated_at: now,
    };
    return [...refs, added];
  }
  if (action.kind === 'remove') return refs.filter((r) => r.id !== action.reference.id);
  const { reference, changes } = action;
  const next = refs.map((r) => {
    if (r.id === reference.id) return { ...r, ...changes };
    return changes.principal ? { ...r, principal: false } : r;
  });
  return [...next].sort((a, b) => Number(b.principal) - Number(a.principal));
}

/** Adding, changing and removing a reference of the card: shown at once
 *  (HR20), the server's article replaces it, undone if refused. */
export function useReferenceMutation(articleId: string) {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (action: ReferenceAction) => {
      if (action.kind === 'add') return addReference(articleId, { pn: action.pn, ncage: action.ncage });
      if (action.kind === 'remove') return removeReference(articleId, action.reference.id, action.reference.version);
      return updateReference(articleId, action.reference.id, action.reference.version, action.changes);
    },
    onMutate: async (action) => {
      await queryClient.cancelQueries({ queryKey: articleKey(articleId) });
      const previous = queryClient.getQueryData<Article>(articleKey(articleId));
      if (previous) {
        const references = referencesAfter(previous.references, action);
        const principal = references.find((r) => r.principal);
        queryClient.setQueryData<Article>(articleKey(articleId), { ...previous, references, pn: principal?.pn ?? null, ncage: principal?.ncage ?? null });
      }
      return { previous };
    },
    onError: (error, _action, context) => {
      if (context?.previous) queryClient.setQueryData(articleKey(articleId), context.previous);
      notifyError(error, t, () => void queryClient.invalidateQueries({ queryKey: articleKey(articleId) }));
    },
    onSuccess: (saved) => {
      queryClient.setQueryData(articleKey(articleId), saved);
      void queryClient.invalidateQueries({ queryKey: ['articles', 'list'] });
      void queryClient.invalidateQueries({ queryKey: ['articles', 'one', articleId, 'history'] });
    },
  });
}

export const revalidationKey = ['articles', 'revalidation'] as const;

/** The last revalidation of every article, polled while it runs; when it
 *  ends, the list (and its findings) is read again. */
export function useLatestRevalidation() {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: revalidationKey,
    queryFn: async () => {
      const before = queryClient.getQueryData<Awaited<ReturnType<typeof fetchLatestRevalidation>>>(revalidationKey);
      const latest = await fetchLatestRevalidation();
      const wasRunning = before && (before.status === 'queued' || before.status === 'running');
      if (wasRunning && latest && latest.id === before.id && latest.status !== before.status) {
        void queryClient.invalidateQueries({ queryKey: ['articles', 'list'] });
        void queryClient.invalidateQueries({ queryKey: ['articles', 'one'] });
      }
      return latest;
    },
    refetchInterval: (query) => (query.state.data && (query.state.data.status === 'queued' || query.state.data.status === 'running') ? 1500 : false),
  });
}

/** The admin's button: not optimistic, the run's id comes from the server. */
export function useStartRevalidation() {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: startRevalidation,
    onSuccess: (run) => queryClient.setQueryData(revalidationKey, run),
    onError: (error) => notifyError(error, t),
  });
}
