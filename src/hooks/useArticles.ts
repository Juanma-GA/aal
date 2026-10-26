import { type InfiniteData, type QueryClient, type QueryKey, useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { notifyError } from '@/lib/notify';
import {
  createArticle,
  deleteArticle,
  fetchArticle,
  fetchArticleHistory,
  fetchArticleRights,
  fetchArticles,
  saveArticleBatch,
  updateArticle,
} from '@/services/articlesApi';
import type { Article, ArticleChanges, ArticleFilters, ArticlePage, ArticleRow, BatchResult } from '@/types/articles';

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
