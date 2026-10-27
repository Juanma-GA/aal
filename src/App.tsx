import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { CHANGE_PASSWORD_PATH, RequireAdmin, RequireAuth } from '@/components/auth/guards';
import { AppLayout } from '@/layouts/AppLayout';
import { ARTICLES_PATH, ArticlePage } from '@/pages/articles/ArticlePage';
import { ArticlesPage } from '@/pages/articles/ArticlesPage';
import { CATALOG_PATH, CatalogPage } from '@/pages/catalog/CatalogPage';
import { ChangePasswordPage } from '@/pages/ChangePasswordPage';
import { MaterialLayout } from '@/layouts/MaterialLayout';
import { ValidationPage } from '@/pages/material/ValidationPage';
import { ConfunfisPage } from '@/pages/material/ConfunfisPage';
import { MaterialCufPage } from '@/pages/material/MaterialCufPage';
import { ModulePage } from '@/pages/ModulePage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { PanelPage } from '@/pages/PanelPage';
import { ARTICLE_FIELDS_PATH, ArticleFieldsPage, REFERENCE_TABLES_PATH, ReferenceTablesPage } from '@/pages/reference/ReferencePages';
import { RootPage } from '@/pages/RootPage';
import { LoginPage } from '@/pages/LoginPage';
import { AuditTab } from '@/pages/settings/AuditTab';
import { MaterialsTab } from '@/pages/settings/MaterialsTab';
import { ModulesTab } from '@/pages/settings/ModulesTab';
import { ValidationRulesTab } from '@/pages/settings/ValidationRulesTab';
import { ParametersTab } from '@/pages/settings/ParametersTab';
import { ArticleFieldsTab, ReferenceTablesTab } from '@/pages/settings/ReferenceTablesTab';
import { RolesTab } from '@/pages/settings/RolesTab';
import { SettingsLayout } from '@/pages/settings/SettingsLayout';
import { UsersTab } from '@/pages/settings/UsersTab';
import { ApiError } from '@/services/apiClient';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // A refused request (4xx) is an answer, not a hiccup: never retried.
      retry: (count, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 1,
    },
  },
});

export function App(): React.JSX.Element {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<RequireAuth />}>
              <Route index element={<RootPage />} />
              <Route path="/materiales/:materialId" element={<MaterialLayout />}>
                <Route index element={<PanelPage />} />
                <Route path="ficha" element={<MaterialCufPage />} />
                <Route path="confunfis" element={<ConfunfisPage />} />
                <Route path="confunfis/:tab" element={<ConfunfisPage />} />
                <Route path="validacion" element={<ValidationPage />} />
                <Route path="modulos/:code" element={<ModulePage />} />
              </Route>
              <Route path={CHANGE_PASSWORD_PATH} element={<ChangePasswordPage />} />
              <Route path={REFERENCE_TABLES_PATH} element={<ReferenceTablesPage />} />
              <Route path={`${REFERENCE_TABLES_PATH}/:code`} element={<ReferenceTablesPage />} />
              <Route path={ARTICLE_FIELDS_PATH} element={<ArticleFieldsPage />} />
              <Route path={CATALOG_PATH} element={<CatalogPage />} />
              <Route path={ARTICLES_PATH} element={<ArticlesPage />} />
              <Route path={`${ARTICLES_PATH}/:articleId`} element={<ArticlePage />} />
              <Route element={<RequireAdmin />}>
                <Route path="/ajustes" element={<SettingsLayout />}>
                  <Route index element={<Navigate to="usuarios" replace />} />
                  <Route path="usuarios" element={<UsersTab />} />
                  <Route path="materiales" element={<MaterialsTab />} />
                  <Route path="roles" element={<RolesTab />} />
                  <Route path="auditoria" element={<AuditTab />} />
                  <Route path="modulos" element={<ModulesTab />} />
                  <Route path="tablas-referencia" element={<ReferenceTablesTab />} />
                  <Route path="tablas-referencia/:code" element={<ReferenceTablesTab />} />
                  <Route path="campos-articulo" element={<ArticleFieldsTab />} />
                  <Route path="parametros" element={<ParametersTab />} />
                  <Route path="reglas-validacion" element={<ValidationRulesTab />} />
                </Route>
              </Route>
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
