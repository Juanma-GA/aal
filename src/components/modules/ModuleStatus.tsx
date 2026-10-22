import { CircleCheck, CircleDashed, Hammer } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { ModuleStatus as Status } from '@/types/modules';

const ICONS = { disponible: CircleCheck, en_desarrollo: Hammer, planificado: CircleDashed } as const;
const COLOURS = { disponible: 'text-success', en_desarrollo: 'text-warning', planificado: 'text-muted-foreground' } as const;

/** The state of a module as an icon, with its text for assistive tech. */
export function ModuleStatusIcon({ status, className }: { status: Status; className?: string }): React.JSX.Element {
  const { t } = useTranslation();
  const Icon = ICONS[status];
  return <Icon className={cn('size-4 shrink-0', COLOURS[status], className)} role="img" aria-label={t(`modules.status.${status}`)} />;
}

export function ModuleStatusBadge({ status }: { status: Status }): React.JSX.Element {
  const { t } = useTranslation();
  return (
    <Badge variant="outline" className="gap-1" data-testid="module-status">
      <ModuleStatusIcon status={status} />
      {t(`modules.status.${status}`)}
    </Badge>
  );
}
