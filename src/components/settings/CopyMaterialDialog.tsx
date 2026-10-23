import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { materialsKey } from '@/hooks/useMaterials';
import { describeApiError } from '@/services/apiErrors';
import { copyMaterial } from '@/services/cufApi';
import type { Material } from '@/types/auth';

// The same formats the server checks (NT 10/17 §9.1.3).
const code = (value: string): string => value.replace(/\s+/g, '').toUpperCase();
const NOC = /^([0-9A-Z]{13})?$/;
const NCAGE = /^([0-9A-Z]{5})?$/;

/** "Crear a partir de otro" (E11): a new CUF with its own name and
 *  identifiers; the rest is copied from `source`. Not optimistic: the id
 *  comes from the server (the documented exception of HR20). */
export function CopyMaterialDialog({ source, onOpenChange }: { source: Material | null; onOpenChange: (open: boolean) => void }): React.JSX.Element {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [noc, setNoc] = useState('');
  const [partNumber, setPartNumber] = useState('');
  const [ncage, setNcage] = useState('');
  const [members, setMembers] = useState(false);
  const copy = useMutation({
    mutationFn: () =>
      copyMaterial(source?.id ?? '', {
        name: name.trim(),
        noc: code(noc) || null,
        part_number: partNumber.trim() || null,
        ncage: code(ncage) || null,
        copy_members: members,
      }),
    onSuccess: (created) => {
      void queryClient.invalidateQueries({ queryKey: materialsKey });
      toast.success(t('settings.materials.copied', { name: created.name }));
      close(false);
    },
  });
  const close = (open: boolean) => {
    if (!open) {
      setName('');
      setNoc('');
      setPartNumber('');
      setNcage('');
      setMembers(false);
      copy.reset();
    }
    onOpenChange(open);
  };
  const nocWrong = !NOC.test(code(noc));
  const ncageWrong = !NCAGE.test(code(ncage));
  return (
    <Dialog open={source !== null} onOpenChange={close}>
      <DialogContent data-testid="copy-material">
        <DialogHeader>
          <DialogTitle>{t('settings.materials.copyTitle', { name: source?.name ?? '' })}</DialogTitle>
          <DialogDescription>{t('settings.materials.copyHint')}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="copy-name">{t('material.fields.name')}</Label>
            <Input id="copy-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={200} />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="copy-noc">{t('material.fields.noc')}</Label>
            <Input id="copy-noc" className="font-mono" value={noc} onChange={(e) => setNoc(e.target.value)} aria-invalid={nocWrong} />
            {nocWrong ? <p className="text-sm text-destructive">{t('validation.noc')}</p> : null}
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="copy-pn">{t('material.fields.part_number')}</Label>
            <Input id="copy-pn" className="font-mono" value={partNumber} onChange={(e) => setPartNumber(e.target.value)} maxLength={32} />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="copy-ncage">{t('material.fields.ncage')}</Label>
            <Input id="copy-ncage" className="font-mono" value={ncage} onChange={(e) => setNcage(e.target.value)} aria-invalid={ncageWrong} />
            {ncageWrong ? <p className="text-sm text-destructive">{t('validation.ncage')}</p> : null}
          </div>
          <div className="flex items-center gap-3">
            <Switch id="copy-members" checked={members} onCheckedChange={setMembers} />
            <Label htmlFor="copy-members">{t('settings.materials.copyMembers')}</Label>
          </div>
          {copy.error ? (
            <p className="text-sm text-destructive" role="alert">
              {describeApiError(copy.error, t).message}
            </p>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => close(false)}>
            {t('actions.cancel')}
          </Button>
          <Button disabled={!name.trim() || nocWrong || ncageWrong || copy.isPending} onClick={() => copy.mutate()} data-testid="copy-save">
            {t('settings.materials.copyAction')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
