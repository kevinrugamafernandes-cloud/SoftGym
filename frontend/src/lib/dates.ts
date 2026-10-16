/** Fechas de calendario (AAAA-MM-DD) en la hora LOCAL del navegador (Costa Rica). */
const pad = (n: number) => String(n).padStart(2, "0");

export const toISODate = (d: Date): string => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

export const todayISO = (): string => toISODate(new Date());

/** "2026-10-16" + 3 → "2026-10-19" (sin pasar por UTC). */
export function addDaysISO(iso: string, days: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  return toISODate(new Date(y, m - 1, d + days));
}

export function startOfMonthISO(iso: string = todayISO()): string {
  return `${iso.slice(0, 8)}01`;
}

export const isISODate = (value: string): boolean =>
  /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value));
