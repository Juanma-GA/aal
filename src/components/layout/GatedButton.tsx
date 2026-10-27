// E17b, for the whole app: a button is hidden only for lack of permission;
// with the permission but a condition missing (no active authorization, an
// outdated validation, a baseline in review, one's own baseline…) it shows
// disabled, saying why (title, and BlockedReason beside it with the link
// that unblocks it). Import and Nueva fila of the CONFUNFIS did it first.
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

/** What a button needs: the permission (else hidden) and, if it is blocked, why and what unblocks it. */
export interface Gate {
  permitted: boolean;
  reason: string | null;
  unlock?: { to: string; label: string } | null;
}

export function GatedButton({ gate, disabled, title, ...props }: React.ComponentProps<typeof Button> & { gate: Gate }): React.JSX.Element | null {
  if (!gate.permitted) return null;
  return (
    <Button {...props} disabled={Boolean(gate.reason) || disabled} title={gate.reason ?? title} data-blocked={gate.reason ? '' : undefined} />
  );
}

/** The reason a gate is closed, with the link to what unblocks it ("Solicitar una autorización", "Validar ahora"). */
export function BlockedReason({ gate, className, testid = 'blocked-reason' }: { gate: Gate; className?: string; testid?: string }): React.JSX.Element | null {
  if (!gate.permitted || !gate.reason) return null;
  return (
    <p className={cn('text-sm text-muted-foreground', className)} data-testid={testid}>
      {gate.reason}
      {gate.unlock ? (
        <>
          {' '}
          <Link to={gate.unlock.to} className="text-link underline-offset-2 hover:underline" data-testid={`${testid}-unlock`}>{gate.unlock.label}</Link>
        </>
      ) : null}
    </p>
  );
}
