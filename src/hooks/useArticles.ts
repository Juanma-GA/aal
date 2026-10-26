import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
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
import type { Article, ArticleChanges, ArticleFilters, ArticleRow } from '@/types/articles';

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

export function useDeleteArticle() {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (article: ArticleRow) => deleteArticle(article.id, article.version),
    onError: (error) => notifyError(error, t),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['articles', 'list'] }),
  });
}

export function useSaveBatch() {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: saveArticleBatch,
    onError: (error) => notifyError(error, t),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['articles', 'list'] }),
  });
}
