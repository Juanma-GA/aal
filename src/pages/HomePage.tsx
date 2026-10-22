import { MaterialCard } from '@/components/MaterialCard';
import { SystemStatusCard } from '@/components/SystemStatusCard';

export function HomePage(): React.JSX.Element {
  return (
    <div className="flex flex-col gap-6">
      <MaterialCard />
      <SystemStatusCard />
    </div>
  );
}
