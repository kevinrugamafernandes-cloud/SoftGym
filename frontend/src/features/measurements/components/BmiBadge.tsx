import { Badge, type BadgeProps } from "@/components/ui/badge";

/** Color según la clasificación OMS que devuelve el servidor ("Peso normal", "Sobrepeso"…). */
function variantFor(category: string): BadgeProps["variant"] {
  if (category.startsWith("Peso normal")) return "success";
  if (category.startsWith("Obesidad")) return "destructive";
  return "warning"; // Bajo peso, Sobrepeso
}

export function BmiBadge({ category }: { category: string | null }) {
  if (!category) return <Badge variant="outline" className="text-muted-foreground">Sin IMC</Badge>;
  return <Badge variant={variantFor(category)}>{category}</Badge>;
}
