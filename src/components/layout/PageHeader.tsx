import { Fragment } from 'react';
import { Link } from 'react-router-dom';
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';

export interface Crumb {
  label: string;
  to?: string;
}

/** Breadcrumbs (material › group › module), the page's heading and the
 *  browser tab's title. */
export function PageHeader({ crumbs, title, children }: { crumbs: Crumb[]; title: string; children?: React.ReactNode }): React.JSX.Element {
  useDocumentTitle(title);
  return (
    <div className="flex flex-col gap-2">
      <Breadcrumb>
        <BreadcrumbList>
          {crumbs.map((crumb, i) => (
            <Fragment key={`${crumb.label}-${i}`}>
              {i > 0 ? <BreadcrumbSeparator /> : null}
              <BreadcrumbItem>
                {crumb.to && i < crumbs.length - 1 ? (
                  <BreadcrumbLink asChild>
                    <Link to={crumb.to}>{crumb.label}</Link>
                  </BreadcrumbLink>
                ) : (
                  <BreadcrumbPage>{crumb.label}</BreadcrumbPage>
                )}
              </BreadcrumbItem>
            </Fragment>
          ))}
        </BreadcrumbList>
      </Breadcrumb>
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-2xl font-semibold text-foreground">{title}</h2>
        {children}
      </div>
    </div>
  );
}
