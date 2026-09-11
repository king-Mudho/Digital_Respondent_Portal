import { Card } from "@/components/ui/card";

export function StatCard({
  label,
  value,
  sublabel,
}: {
  label: string;
  value: React.ReactNode;
  sublabel?: string;
}) {
  return (
    <Card className="space-y-1">
      <p className="text-xs uppercase tracking-wide text-text-muted">{label}</p>
      <p className="text-2xl font-semibold tabular-nums">{value}</p>
      {sublabel && <p className="text-sm text-text-muted">{sublabel}</p>}
    </Card>
  );
}
