// The CONFUNFIS's change-control band (E17): which baseline it is under,
// how many changes since, and, when a reviewed baseline asks for one, the
// authorization the edits go under (chosen here, sent by apiClient).
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useActiveAuthorization, useConfigurationState } from '@/hooks/useBaselines';
import { useUiStore } from '@/stores/uiStore';

const NONE = '-';

export function ConfigurationBand({ materialId, canRequest }: { materialId: string; canRequest: boolean }): React.JSX.Element | null {
  const { t } = useTranslation();
  const state = useConfigurationState(materialId);
  const active = useActiveAuthorization(materialId);
  const choose = useUiStore((s) => s.setChangeAuthorization);
  const s = state.data;
  if (!s || (!s.reviewed && !s.in_review)) return null;
  const page = `/materiales/${materialId}/baselines`;
  if (s.edit === 'locked' && s.in_review) {
    return (
      <Alert data-testid="confunfis-band" data-state="locked">
        <AlertDescription>
          {t('baselines.band.locked', { number: s.in_review.number })}{' '}
          <Link to={page} className="text-link underline-offset-2 hover:underline">{t('baselines.band.open')}</Link>
        </AlertDescription>
      </Alert>
    );
  }
  return (
    <Alert data-testid="confunfis-band" data-state={s.edit}>
      <AlertDescription className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span>
          {t('baselines.band.reviewed', { number: s.reviewed?.number })} · {t('baselines.band.changesSince', { count: s.changes_since, number: s.reviewed?.number })}
        </span>
        {s.usable_authorizations.length > 0 ? (
          <span className="flex items-center gap-2">
            <span>{t('baselines.band.active')}</span>
            <Select value={active?.id ?? NONE} onValueChange={(v) => choose(materialId, v === NONE ? null : v)}>
              <SelectTrigger className="h-8 w-56" aria-label={t('baselines.band.active')} data-testid="confunfis-authorization">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>{t('baselines.band.noneChosen')}</SelectItem>
                {s.usable_authorizations.map((a) => (
                  <SelectItem key={a.id} value={a.id} data-testid={`confunfis-authorization-${a.code}`}>
                    {a.code} · {a.description}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </span>
        ) : (
          <span className="text-muted-foreground">{t('baselines.band.noneUsable')}</span>
        )}
        <Link to={canRequest ? `${page}?tab=autorizaciones` : page} className="text-link underline-offset-2 hover:underline">
          {canRequest ? t('baselines.band.request') : t('baselines.band.open')}
        </Link>
      </AlertDescription>
    </Alert>
  );
}
