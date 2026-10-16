import { Link } from "react-router-dom";
import { Dumbbell, MoveLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 text-center">
      {/* Ambient glow */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 overflow-hidden"
      >
        <div className="absolute top-1/3 left-1/2 h-64 w-64 -translate-x-1/2 -translate-y-1/2 rounded-full bg-gold/5 blur-3xl" />
      </div>

      <div className="relative">
        <div className="mb-6 flex items-center justify-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gold/10 border border-gold/20">
            <Dumbbell className="h-8 w-8 text-gold" />
          </div>
        </div>

        <h1 className="text-7xl font-bold text-foreground">404</h1>
        <h2 className="mt-3 text-xl font-semibold text-foreground">
          Página no encontrada
        </h2>
        <p className="mt-2 max-w-sm text-sm text-muted-foreground">
          La ruta que buscas no existe o fue movida. Vuelve al dashboard
          para continuar.
        </p>

        <Button variant="gold" className="mt-8" asChild>
          <Link to="/dashboard">
            <MoveLeft className="mr-2 h-4 w-4" />
            Volver al dashboard
          </Link>
        </Button>
      </div>
    </div>
  );
}
