import { ChevronRight, Settings } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router-dom';
import { ModuleStatusIcon } from '@/components/modules/ModuleStatus';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from '@/components/ui/sidebar';
import { Skeleton } from '@/components/ui/skeleton';
import { useActiveMaterial } from '@/hooks/useMaterials';
import { moduleHref, useModules } from '@/hooks/useModules';
import { useMe } from '@/hooks/useSession';
import { useSidebarGroups } from '@/hooks/useSidebarGroups';

/** The whole PALI, from the module catalog: groups that fold (kept in the
 *  user's preferences), each module with its state; an available module
 *  opens itself, the rest their card. Settings at the foot, admins only. */
export function AppSidebar(): React.JSX.Element {
  const { t } = useTranslation();
  const me = useMe();
  const modules = useModules();
  const material = useActiveMaterial();
  const location = useLocation();
  const { collapsed, toggle } = useSidebarGroups();
  const { isMobile, setOpenMobile } = useSidebar();
  const close = () => isMobile && setOpenMobile(false);

  return (
    <Sidebar data-testid="app-sidebar">
      <SidebarContent>
        {!modules.data ? (
          <div className="flex flex-col gap-2 p-4">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-5 w-32" />
          </div>
        ) : !material ? (
          <p className="p-4 text-sm text-muted-foreground">{t('nav.noMaterial')}</p>
        ) : (
          modules.data.map((group) => {
            const open = !collapsed.includes(group.code);
            return (
              <Collapsible key={group.code} open={open} onOpenChange={() => toggle(group.code)}>
                <SidebarGroup data-testid={`sidebar-group-${group.code}`}>
                  <SidebarGroupLabel asChild>
                    <CollapsibleTrigger className="w-full justify-between text-left" aria-expanded={open}>
                      <span className="truncate">{group.name}</span>
                      <ChevronRight aria-hidden="true" className={open ? 'rotate-90 transition-transform' : 'transition-transform'} />
                    </CollapsibleTrigger>
                  </SidebarGroupLabel>
                  <CollapsibleContent>
                    <SidebarGroupContent>
                      <SidebarMenu>
                        {group.modules.map((m) => {
                          const href = moduleHref(m, material.id);
                          return (
                            <SidebarMenuItem key={m.code}>
                              <SidebarMenuButton asChild isActive={location.pathname === href} className="h-auto py-1.5">
                                <Link to={href} onClick={close} data-testid={`sidebar-module-${m.code}`} data-status={m.status}>
                                  <ModuleStatusIcon status={m.status} />
                                  <span className="whitespace-normal">{m.name}</span>
                                </Link>
                              </SidebarMenuButton>
                            </SidebarMenuItem>
                          );
                        })}
                      </SidebarMenu>
                    </SidebarGroupContent>
                  </CollapsibleContent>
                </SidebarGroup>
              </Collapsible>
            );
          })
        )}
      </SidebarContent>
      {me.data?.is_admin ? (
        <SidebarFooter>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton asChild isActive={location.pathname.startsWith('/ajustes')}>
                <Link to="/ajustes" onClick={close} data-testid="settings-link">
                  <Settings aria-hidden="true" />
                  <span>{t('header.settings')}</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
      ) : null}
    </Sidebar>
  );
}
