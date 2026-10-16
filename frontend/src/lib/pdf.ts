import axios from "axios";
import { reportError } from "@/lib/report-error";
import { toast } from "@/hooks/useToast";

/**
 * Con responseType "blob" el cuerpo de un error también llega como Blob y getErrorMessage()
 * no puede leer su `detail`. Se convierte de vuelta a JSON para conservar el mensaje en español.
 */
export async function unwrapBlobError(error: unknown): Promise<never> {
  if (axios.isAxiosError(error) && error.response?.data instanceof Blob) {
    try {
      error.response.data = JSON.parse(await error.response.data.text());
    } catch {
      /* no era JSON: se deja como está */
    }
  }
  throw error;
}

/**
 * Abre un PDF protegido (lleva el token) en una pestaña nueva.
 * La pestaña se abre SINCRÓNICAMENTE en el clic (si se abriera después del await, el navegador
 * la bloquearía como ventana emergente) y luego recibe el PDF. Si aun así se bloquea, se descarga.
 */
export async function openPdf(fetchPdf: () => Promise<Blob>, title: string, filename: string): Promise<void> {
  const win = window.open("", "_blank");
  if (win) {
    win.document.title = title;
    win.document.body.style.cssText = "background:#0b0b0c;color:#aaa;font:14px system-ui;padding:24px";
    win.document.body.textContent = "Generando documento…";
  }
  try {
    const blob = await fetchPdf();
    const url = URL.createObjectURL(new Blob([blob], { type: "application/pdf" }));
    if (win && !win.closed) {
      win.location.href = url;
    } else {
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      toast({ title: "Documento descargado", description: `Se descargó ${filename}` });
    }
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch (err) {
    win?.close();
    reportError(err, "No se pudo generar el documento");
  }
}

/** Descarga un archivo protegido (CSV, PDF…) con el nombre indicado. */
export async function downloadFile(fetchFile: () => Promise<Blob>, filename: string): Promise<boolean> {
  try {
    const blob = await fetchFile();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
    toast({ variant: "success", title: "Archivo descargado", description: filename });
    return true;
  } catch (err) {
    reportError(err, "No se pudo descargar el archivo");
    return false;
  }
}
