import { cn } from "@/utils";

export type StatTone = "gold" | "danger" | "success" | "muted";

/** Cifra destacada con etiqueta y nota (totales de pagos, caja, etc.). */
export function StatTile({ label, value, hint, tone = "muted", className }: {
  label: string; value: string; hint?: string; tone?: StatTone; className?: string;
}) {
  return (
    <div className={cn("rounded-lg border border-border bg-input/30 p-4", className)}>
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={cn(
        "mt-1 text-xl font-semibold tabular-nums",
        tone === "gold" && "text-gold", tone === "danger" && "text-destructive",
        tone === "success" && "text-success", tone === "muted" && "text-foreground"
      )}>{value}</p>
      {hint && <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
