import { useQueryClient } from '@tanstack/react-query';
import { ChevronDown } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { CHANGE_PASSWORD_PATH } from '@/components/auth/guards';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useMe } from '@/hooks/useSession';
import { ARTICLE_FIELDS_PATH, REFERENCE_TABLES_PATH } from '@/pages/reference/ReferencePages';
import { logout } from '@/services/authApi';

export function UserMenu(): React.JSX.Element | null {
  const { t } = useTranslation();
  const me = useMe();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  if (!me.data) return null;
  const signOut = async () => {
    try {
      await logout();
    } finally {
      await queryClient.resetQueries();
      navigate('/login', { replace: true });
    }
  };
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost" className="text-header-control-foreground hover:bg-header-accent hover:text-header-control-foreground"
          aria-label={t('header.userMenu', { name: me.data.display_name })} data-testid="user-menu"
        >
          <span className="max-w-40 truncate">{me.data.display_name}</span>
          <ChevronDown aria-hidden="true" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel className="font-normal text-muted-foreground">{me.data.email}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => navigate(REFERENCE_TABLES_PATH)} data-testid="reference-tables-link">
          {t('header.referenceTables')}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => navigate(ARTICLE_FIELDS_PATH)}>{t('header.articleFields')}</DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => navigate(CHANGE_PASSWORD_PATH)}>{t('actions.changePassword')}</DropdownMenuItem>
        <DropdownMenuItem onSelect={() => void signOut()} data-testid="sign-out">
          {t('actions.signOut')}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
