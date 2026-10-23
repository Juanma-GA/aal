// A table row that opens something (E11): the whole row is clickable, with
// a visible affordance (the chevron) and the row's main link still the
// keyboard way in. A click on a button, link or menu inside the row does
// its own thing.
import { ChevronRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { TableCell, TableRow } from '@/components/ui/table';
import { cn } from '@/lib/utils';

const INTERACTIVE = 'a, button, input, select, textarea, [role="menuitem"], [role="checkbox"]';

export function NavRow({ to, onOpen, className, children, label, ...props }: {
  /** Where the row goes, or `onOpen` for something other than a route. */
  to?: string;
  onOpen?: () => void;
  /** What opening it does, for the chevron's accessible name. */
  label: string;
  className?: string;
  children: React.ReactNode;
} & Omit<React.ComponentProps<typeof TableRow>, 'onClick'>): React.JSX.Element {
  const navigate = useNavigate();
  const open = () => (onOpen ? onOpen() : to && navigate(to));
  return (
    <TableRow
      {...props}
      data-nav-row=""
      className={cn('cursor-pointer', className)}
      onClick={(e) => {
        // Clicks inside a portal (a row's menu) bubble here too: not the row's own.
        if (!e.currentTarget.contains(e.target as Node) || (e.target as HTMLElement).closest(INTERACTIVE)) return;
        open();
      }}
    >
      {children}
      <TableCell className="w-8 text-right">
        <button type="button" onClick={open} aria-label={label} className="inline-flex size-6 items-center justify-center rounded text-muted-foreground hover:text-foreground">
          <ChevronRight className="size-4" aria-hidden="true" />
        </button>
      </TableCell>
    </TableRow>
  );
}
