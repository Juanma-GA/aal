import { useRef } from 'react';
import { useTranslation } from 'react-i18next';
import type { SidebarLayout } from '@/hooks/useSidebarLayout';
import { cn } from '@/lib/utils';

const STEP = 16;

/** The sidebar's edge: dragged (or moved with the arrow keys) it changes the
 *  width within the "ui" parameter's limits; a double click goes back to the
 *  default. Saved when the drag ends. */
export function SidebarResizer({ layout }: { layout: SidebarLayout }): React.JSX.Element | null {
  const { t } = useTranslation();
  const start = useRef<{ x: number; width: number } | null>(null);
  const { limits, side, width } = layout;
  if (!limits) return null;
  // Dragging away from the content widens it, on either side.
  const widthAt = (x: number) => (start.current ? start.current.width + (side === 'left' ? x - start.current.x : start.current.x - x) : width);
  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={t('nav.resizeSidebar')}
      aria-valuemin={limits.min}
      aria-valuemax={limits.max}
      aria-valuenow={width}
      tabIndex={0}
      data-testid="sidebar-resizer"
      title={t('nav.resizeSidebar')}
      className={cn(
        'absolute inset-y-0 z-20 hidden w-1.5 cursor-col-resize touch-none bg-transparent outline-none hover:bg-sidebar-border focus-visible:bg-ring md:block',
        'group-data-[collapsible=icon]:hidden',
        side === 'left' ? '-right-0.5' : '-left-0.5',
      )}
      onPointerDown={(e) => {
        e.preventDefault();
        e.currentTarget.setPointerCapture(e.pointerId);
        start.current = { x: e.clientX, width };
      }}
      onPointerMove={(e) => {
        if (start.current) layout.setWidth(widthAt(e.clientX), false);
      }}
      onPointerUp={(e) => {
        if (!start.current) return;
        layout.setWidth(widthAt(e.clientX), true);
        start.current = null;
      }}
      onPointerCancel={() => {
        start.current = null;
      }}
      onDoubleClick={() => layout.setWidth(limits.default, true)}
      onKeyDown={(e) => {
        const wider = side === 'left' ? 'ArrowRight' : 'ArrowLeft';
        const narrower = side === 'left' ? 'ArrowLeft' : 'ArrowRight';
        if (e.key === wider || e.key === narrower) {
          e.preventDefault();
          layout.setWidth(width + (e.key === wider ? STEP : -STEP), true);
        }
      }}
    />
  );
}
