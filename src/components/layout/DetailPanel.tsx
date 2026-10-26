// The detail panel of a list (E15): docked beside the content from 1024 px
// -- the content narrows, nothing is darkened, the list stays visible and
// clickable -- and an overlay (the shadcn sheet) below. Its width is dragged
// by its left edge and kept per user on the server (useDetailPanelWidth).
// Closed with its ×, with Esc, or by the page when its row is clicked again.
import { X } from 'lucide-react';
import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { useDetailPanelWidth, useDocked } from '@/hooks/useDetailPanel';
import { useUiStore } from '@/stores/uiStore';

const STEP = 16;

interface Props {
  title: React.ReactNode;
  description?: React.ReactNode;
  onClose: () => void;
  children: React.ReactNode;
  testId?: string;
  /** The overlay's width below 1024 px (a Tailwind max-width class). */
  overlayClassName?: string;
}

/** A dialog of the page (a confirmation, a form) is open: Esc is its. */
const dialogOpen = () => Boolean(document.querySelector('[role="dialog"][data-state="open"], [role="alertdialog"][data-state="open"]'));

function Resizer(): React.JSX.Element | null {
  const { t } = useTranslation();
  const { width, limits, setWidth } = useDetailPanelWidth();
  const start = useRef<{ x: number; width: number } | null>(null);
  if (!limits) return null;
  // The edge is on the left: dragging it left widens the panel.
  const widthAt = (x: number) => (start.current ? start.current.width + start.current.x - x : width);
  return (
    <div
      role="separator" aria-orientation="vertical" aria-label={t('detailPanel.resize')} title={t('detailPanel.resize')}
      aria-valuemin={limits.min} aria-valuemax={limits.max} aria-valuenow={width} tabIndex={0} data-testid="detail-panel-resizer"
      className="absolute inset-y-0 -left-0.5 z-20 w-1.5 cursor-col-resize touch-none bg-transparent outline-none hover:bg-border focus-visible:bg-ring"
      onPointerDown={(e) => { e.preventDefault(); e.currentTarget.setPointerCapture(e.pointerId); start.current = { x: e.clientX, width }; }}
      onPointerMove={(e) => { if (start.current) setWidth(widthAt(e.clientX), false); }}
      onPointerUp={(e) => { if (!start.current) return; setWidth(widthAt(e.clientX), true); start.current = null; }}
      onPointerCancel={() => { start.current = null; }}
      onDoubleClick={() => setWidth(limits.default, true)}
      onKeyDown={(e) => {
        if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
          e.preventDefault();
          setWidth(width + (e.key === 'ArrowLeft' ? STEP : -STEP), true);
        }
      }}
    />
  );
}

export function DetailPanel({ title, description, onClose, children, testId, overlayClassName = 'sm:max-w-xl' }: Props): React.JSX.Element {
  const { t } = useTranslation();
  const docked = useDocked();
  const { width } = useDetailPanelWidth();
  // AppLayout's slot beside <main> (signed in); without it, an overlay.
  const slot = useUiStore((s) => s.detailSlot);
  const close = useRef(onClose);
  useEffect(() => {
    close.current = onClose;
  });
  useEffect(() => {
    if (!docked) return undefined;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !e.defaultPrevented && !dialogOpen()) close.current();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [docked]);

  if (!docked || !slot) {
    return (
      <Sheet open onOpenChange={(open) => { if (!open) onClose(); }}>
        <SheetContent className={`w-full overflow-y-auto ${overlayClassName}`} data-testid={testId}>
          <SheetHeader>
            <SheetTitle>{title}</SheetTitle>
            <SheetDescription>{description ?? ''}</SheetDescription>
          </SheetHeader>
          {children}
        </SheetContent>
      </Sheet>
    );
  }
  return createPortal(
    <aside
      aria-label={typeof title === 'string' ? title : t('detailPanel.label')}
      className="relative sticky top-0 h-svh shrink-0 overflow-y-auto border-l bg-background"
      style={{ width }}
      data-testid={testId}
      data-docked="true"
    >
      <Resizer />
      <div className="flex items-start gap-2 border-b p-4">
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <h2 className="font-semibold text-foreground">{title}</h2>
          {description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
        </div>
        <Button variant="ghost" size="icon" aria-label={t('detailPanel.close')} onClick={onClose} data-testid="detail-panel-close">
          <X aria-hidden="true" />
        </Button>
      </div>
      <div className="pt-4">{children}</div>
    </aside>,
    slot,
  );
}
