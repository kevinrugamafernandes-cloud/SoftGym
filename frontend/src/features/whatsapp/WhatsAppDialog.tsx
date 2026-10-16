import { useState } from "react";
import { AlertCircle, Copy, MessageCircle } from "lucide-react";

import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/hooks/useToast";
import { getErrorMessage } from "@/lib/axios";
import type { WhatsAppLink } from "@/types";

interface WhatsAppDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Qué se envía, p. ej. "el comprobante V-000012". */
  subject: string;
  defaultPhone?: string | null;
  /** Pide al backend el enlace wa.me con el mensaje ya armado. */
  fetchLink: (phone: string) => Promise<WhatsAppLink>;
}

/**
 * Envío por WhatsApp con enlace directo (wa.me): abre WhatsApp Web o la app con el mensaje
 * escrito; la recepcionista solo presiona «Enviar». Sin API de Meta ni costos.
 */
export function WhatsAppDialog({ open, onOpenChange, subject, defaultPhone, fetchLink }: WhatsAppDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><MessageCircle className="h-5 w-5 text-success" aria-hidden /> Enviar por WhatsApp</DialogTitle>
          <DialogDescription>Se abrirá WhatsApp con {subject} ya escrito. Revise y presione «Enviar».</DialogDescription>
        </DialogHeader>
        {open && <WhatsAppForm defaultPhone={defaultPhone} fetchLink={fetchLink} onClose={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  );
}

function WhatsAppForm({ defaultPhone, fetchLink, onClose }: {
  defaultPhone?: string | null; fetchLink: (phone: string) => Promise<WhatsAppLink>; onClose: () => void;
}) {
  const [phone, setPhone] = useState(defaultPhone ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [link, setLink] = useState<WhatsAppLink | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    e.stopPropagation(); // puede abrirse dentro de otro formulario (ver OpenCashDialog)
    setError(null);
    if (phone.replace(/\D/g, "").length < 8) {
      setError("Indique un número de WhatsApp válido (8 dígitos en Costa Rica).");
      return;
    }
    // La pestaña se abre en el clic: si se abriera tras el await, el navegador la bloquearía.
    const win = window.open("", "_blank");
    setBusy(true);
    try {
      const l = await fetchLink(phone);
      setLink(l);
      if (win && !win.closed) {
        win.opener = null;
        win.location.href = l.url;
      } else {
        window.location.assign(l.url);
      }
    } catch (err) {
      win?.close();
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link.message);
      toast({ variant: "success", title: "Mensaje copiado" });
    } catch {
      toast({ variant: "destructive", title: "No se pudo copiar", description: "Seleccione el texto y cópielo manualmente." });
    }
  };

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      {error && (
        <Alert variant="destructive" icon={<AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
          <AlertDescription className="text-foreground">{error}</AlertDescription>
        </Alert>
      )}
      <div className="space-y-1.5">
        <Label htmlFor="wa-phone">Número de WhatsApp</Label>
        <Input id="wa-phone" type="tel" inputMode="tel" autoComplete="off" autoFocus placeholder="8888-1234"
          value={phone} onChange={(e) => setPhone(e.target.value)} />
        <p className="text-xs text-muted-foreground">Números de 8 dígitos se envían con el prefijo de Costa Rica (+506).</p>
      </div>
      {link && (
        <div className="space-y-2">
          <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap rounded-lg border border-border bg-input/30 p-3 font-sans text-xs text-muted-foreground">{link.message}</pre>
          <p className="text-xs text-muted-foreground">
            ¿No se abrió WhatsApp? <a href={link.url} target="_blank" rel="noreferrer" className="text-gold hover:underline">Abrir enlace</a> o copie el mensaje.
          </p>
        </div>
      )}
      <DialogFooter>
        {link ? (
          <Button type="button" variant="outline" onClick={() => void copy()}><Copy className="mr-2 h-4 w-4" aria-hidden /> Copiar mensaje</Button>
        ) : (
          <Button type="button" variant="outline" onClick={onClose} disabled={busy}>Cancelar</Button>
        )}
        <Button type="submit" variant="gold" loading={busy}>
          <MessageCircle className="mr-2 h-4 w-4" aria-hidden /> {link ? "Abrir de nuevo" : "Abrir WhatsApp"}
        </Button>
      </DialogFooter>
    </form>
  );
}
