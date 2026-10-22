import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';

interface Props {
  name: string;
  password: string | null;
  onClose: () => void;
}

/** The temporary password, shown once: the server never gives it again. */
export function TemporaryPasswordDialog({ name, password, onClose }: Props): React.JSX.Element {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    if (!password) return;
    await navigator.clipboard.writeText(password);
    setCopied(true);
  };
  return (
    <Dialog
      open={password !== null}
      onOpenChange={(open) => {
        if (!open) {
          setCopied(false);
          onClose();
        }
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('settings.users.temporaryTitle', { name })}</DialogTitle>
          <DialogDescription>{t('settings.users.temporaryHint')}</DialogDescription>
        </DialogHeader>
        <p className="rounded-md border bg-muted px-3 py-2 font-mono text-lg text-foreground select-all" data-testid="temporary-password">
          {password}
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={() => void copy()}>
            {copied ? t('actions.copied') : t('actions.copy')}
          </Button>
          <Button onClick={onClose}>{t('actions.close')}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
