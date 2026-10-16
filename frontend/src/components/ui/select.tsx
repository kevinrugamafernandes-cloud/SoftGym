import * as React from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/utils";

/** <select> nativo con el estilo de SoftGym: accesible, móvil-friendly y sin dependencias. */
const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => (
    <div className="relative">
      <select
        ref={ref}
        className={cn(
          "flex h-10 w-full appearance-none rounded-md border border-input bg-input px-3 pr-9 text-sm text-foreground",
          "[color-scheme:dark] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          "disabled:cursor-not-allowed disabled:opacity-50 transition-colors",
          className
        )}
        {...props}
      >
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute right-3 top-3 h-4 w-4 text-muted-foreground" aria-hidden />
    </div>
  )
);
Select.displayName = "Select";

export { Select };
