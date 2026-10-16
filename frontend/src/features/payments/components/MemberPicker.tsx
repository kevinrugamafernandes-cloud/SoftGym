import { useEffect, useId, useState } from "react";
import { Loader2, Search, UserRound, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MemberStatusBadge } from "@/features/members/components/MemberStatusBadge";
import { useDebounce } from "@/hooks/useDebounce";
import { useMembers } from "@/hooks/useMembers";
import { cn } from "@/utils";
import type { Member } from "@/types";

import { MembershipStateText } from "./MembershipStateText";

interface MemberPickerProps {
  value: Member | null;
  onChange: (member: Member | null) => void;
  invalid?: boolean;
  /** Si se abrió desde la ficha del socio, no se permite cambiarlo. */
  locked?: boolean;
  autoFocus?: boolean;
  /** id del cuadro de búsqueda (para asociarlo a su <Label htmlFor>). */
  id?: string;
}

/**
 * Buscador de socio por nombre o cédula (combobox accesible).
 * Flechas ↑/↓ para moverse, Enter para elegir (sin enviar el formulario), Esc para cerrar.
 */
export function MemberPicker({ value, onChange, invalid, locked, autoFocus, id }: MemberPickerProps) {
  const listId = useId();
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const search = useDebounce(text.trim(), 300);

  const results = useMembers({ search, status: "", page: 1, size: 6 });
  const items = search.length >= 2 ? results.data?.items ?? [] : [];

  useEffect(() => setActive(0), [search]);

  if (value) {
    return (
      <div
        className={cn(
          "flex items-start gap-3 rounded-lg border border-border bg-input/40 p-3",
          invalid && "border-destructive"
        )}
      >
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gold/10 text-gold">
          <UserRound className="h-4 w-4" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate text-sm font-medium text-foreground">{value.full_name}</p>
            <MemberStatusBadge status={value.status} />
          </div>
          <p className="text-xs text-muted-foreground tabular-nums">Cédula {value.identification}</p>
          <MembershipStateText membership={value.membership} className="mt-1" />
        </div>
        {!locked && (
          <Button
            type="button" variant="ghost" size="sm" className="shrink-0 text-muted-foreground"
            onClick={() => { onChange(null); setText(""); setOpen(true); }}
          >
            <X className="mr-1 h-4 w-4" aria-hidden /> Cambiar
          </Button>
        )}
      </div>
    );
  }

  const pick = (m: Member) => {
    onChange(m);
    setOpen(false);
    setText("");
  };

  const showList = open && search.length >= 2;
  const loading = results.isFetching && text.trim() === search;

  return (
    <div className="relative">
      <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" aria-hidden />
      <Input
        id={id}
        role="combobox"
        aria-expanded={showList}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-invalid={invalid}
        aria-activedescendant={showList && items[active] ? `${listId}-${active}` : undefined}
        autoFocus={autoFocus}
        autoComplete="off"
        placeholder="Buscar socio por nombre o cédula…"
        className={cn("pl-9 pr-9", invalid && "border-destructive focus-visible:ring-destructive")}
        value={text}
        onChange={(e) => { setText(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true); setActive((i) => Math.min(i + 1, items.length - 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
          else if (e.key === "Enter") {
            // Enter elige el socio resaltado; nunca envía el formulario desde el buscador.
            e.preventDefault();
            if (items[active]) pick(items[active]);
          } else if (e.key === "Escape" && open) { e.preventDefault(); e.stopPropagation(); setOpen(false); }
        }}
      />
      {loading && <Loader2 className="absolute right-3 top-3 h-4 w-4 animate-spin text-muted-foreground" aria-hidden />}

      {showList && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-50 mt-1 max-h-72 w-full overflow-y-auto rounded-lg border border-border bg-card p-1 shadow-xl shadow-black/40"
        >
          {results.isError && (
            <li className="px-3 py-2 text-sm text-destructive">No se pudo buscar. Intente de nuevo.</li>
          )}
          {!results.isError && !loading && items.length === 0 && (
            <li className="px-3 py-2 text-sm text-muted-foreground">Ningún socio coincide con «{search}».</li>
          )}
          {items.map((m, i) => (
            <li
              key={m.id}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => e.preventDefault()} // evita el blur antes del clic
              onClick={() => pick(m)}
              onMouseEnter={() => setActive(i)}
              className={cn(
                "flex cursor-pointer items-center justify-between gap-3 rounded-md px-3 py-2 text-sm",
                i === active ? "bg-accent text-foreground" : "text-muted-foreground"
              )}
            >
              <span className="min-w-0">
                <span className="block truncate text-foreground">{m.full_name}</span>
                <span className="block text-xs tabular-nums">{m.identification}</span>
              </span>
              <MemberStatusBadge status={m.status} className="shrink-0" />
            </li>
          ))}
        </ul>
      )}
      {!showList && text.trim().length > 0 && text.trim().length < 2 && (
        <p className="mt-1 text-xs text-muted-foreground">Escriba al menos 2 caracteres.</p>
      )}
    </div>
  );
}
