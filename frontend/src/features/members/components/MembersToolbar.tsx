import { ArchiveRestore, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { SearchInput } from "@/components/common/SearchInput";
import { MEMBER_STATUS_LABELS } from "@/lib/labels";
import type { MemberStatus } from "@/types";

interface MembersToolbarProps {
  searchText: string;
  onSearchText: (value: string) => void;
  status: MemberStatus | "";
  onStatus: (value: MemberStatus | "") => void;
  searching: boolean;
  canCreate: boolean;
  onCreate: () => void;
  canRestore: boolean;
  onRestore: () => void;
}

const STATUS_OPTIONS: MemberStatus[] = ["activo", "inactivo", "por_vencer", "moroso"];

export function MembersToolbar({
  searchText, onSearchText, status, onStatus, searching, canCreate, onCreate, canRestore, onRestore,
}: MembersToolbarProps) {
  return (
    <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
      <SearchInput
        className="flex-1 lg:max-w-md"
        value={searchText}
        onValueChange={onSearchText}
        loading={searching}
        placeholder="Buscar por nombre, apellidos o cédula…"
        aria-label="Buscar socios por nombre, apellidos o cédula"
      />

      <div className="flex flex-1 flex-wrap items-center gap-2 lg:justify-end">
        <div className="w-full sm:w-44">
          <Select
            value={status}
            onChange={(e) => onStatus(e.target.value as MemberStatus | "")}
            aria-label="Filtrar por estado"
          >
            <option value="">Todos los estados</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>{MEMBER_STATUS_LABELS[s]}</option>
            ))}
          </Select>
        </div>

        {canRestore && (
          <Button variant="outline" onClick={onRestore}>
            <ArchiveRestore className="mr-2 h-4 w-4" aria-hidden /> Restaurar socio
          </Button>
        )}
        {canCreate && (
          <Button variant="gold" onClick={onCreate}>
            <Plus className="mr-2 h-4 w-4" aria-hidden /> Inscribir socio
          </Button>
        )}
      </div>
    </div>
  );
}
