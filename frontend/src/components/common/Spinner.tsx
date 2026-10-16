import { Loader2 } from "lucide-react";
import { cn } from "@/utils";

export function Spinner({ className }: { className?: string }) {
  return <Loader2 aria-hidden className={cn("h-4 w-4 animate-spin", className)} />;
}
