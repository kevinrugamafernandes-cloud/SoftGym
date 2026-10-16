import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils";

interface PaginationProps {
  page: number;
  pages: number;
  total: number;
  size: number;
  onPageChange: (page: number) => void;
  disabled?: boolean;
  className?: string;
}

/** Números de página con elipsis: 1 … 4 5 [6] 7 8 … 20 */
function pageWindow(page: number, pages: number): (number | "…")[] {
  if (pages <= 7) return Array.from({ length: pages }, (_, i) => i + 1);
  const out: (number | "…")[] = [1];
  const start = Math.max(2, page - 1);
  const end = Math.min(pages - 1, page + 1);
  if (start > 2) out.push("…");
  for (let p = start; p <= end; p++) out.push(p);
  if (end < pages - 1) out.push("…");
  out.push(pages);
  return out;
}

export function Pagination({ page, pages, total, size, onPageChange, disabled, className }: PaginationProps) {
  if (total === 0) return null;
  const from = (page - 1) * size + 1;
  const to = Math.min(page * size, total);

  return (
    <nav
      aria-label="Paginación"
      className={cn("flex flex-col items-center justify-between gap-3 sm:flex-row", className)}
    >
      <p className="text-sm text-muted-foreground" aria-live="polite">
        Mostrando <span className="font-medium text-foreground">{from}–{to}</span> de{" "}
        <span className="font-medium text-foreground">{total}</span>
      </p>

      {pages > 1 && (
        <div className="flex items-center gap-1">
          <Button
            variant="outline" size="sm" disabled={disabled || page <= 1}
            onClick={() => onPageChange(page - 1)} aria-label="Página anterior"
          >
            <ChevronLeft className="h-4 w-4" />
            <span className="ml-1 hidden sm:inline">Anterior</span>
          </Button>

          <div className="hidden items-center gap-1 sm:flex">
            {pageWindow(page, pages).map((p, i) =>
              p === "…" ? (
                <span key={`gap-${i}`} className="px-2 text-muted-foreground" aria-hidden>…</span>
              ) : (
                <Button
                  key={p} size="sm" variant={p === page ? "gold" : "ghost"} disabled={disabled}
                  className="min-w-9 px-2" onClick={() => onPageChange(p)}
                  aria-label={`Página ${p}`} aria-current={p === page ? "page" : undefined}
                >
                  {p}
                </Button>
              )
            )}
          </div>
          <span className="px-2 text-sm text-muted-foreground sm:hidden">{page} / {pages}</span>

          <Button
            variant="outline" size="sm" disabled={disabled || page >= pages}
            onClick={() => onPageChange(page + 1)} aria-label="Página siguiente"
          >
            <span className="mr-1 hidden sm:inline">Siguiente</span>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </nav>
  );
}
