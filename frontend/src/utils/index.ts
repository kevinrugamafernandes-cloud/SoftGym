import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind classes without conflicts. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Convierte "AAAA-MM-DD" en una fecha LOCAL. `new Date("2026-09-30")` la interpreta como
 * medianoche UTC y, en Costa Rica (UTC-6), mostraría el día anterior.
 */
function parseDate(dateStr: string): Date {
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateStr);
  return dateOnly
    ? new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]))
    : new Date(dateStr);
}

/** Format a date string to a readable locale format. */
export function formatDate(
  dateStr: string | null | undefined,
  options: Intl.DateTimeFormatOptions = {
    year: "numeric",
    month: "short",
    day: "numeric",
  }
): string {
  if (!dateStr) return "—";
  const date = parseDate(dateStr);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString("es-CR", options);
}

/** Capitalise the first letter of a string. */
export function capitalize(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

/** Return initials from a full name (max 2 chars). */
export function getInitials(fullName: string): string {
  return fullName
    .split(" ")
    .slice(0, 2)
    .map((n) => n[0])
    .join("")
    .toUpperCase();
}

/** "88881234" → "8888-1234"; "+50688881234" → "+506 8888-1234". Otro formato se deja igual. */
export function formatPhone(phone: string | null | undefined): string {
  if (!phone) return "—";
  if (/^\d{8}$/.test(phone)) return `${phone.slice(0, 4)}-${phone.slice(4)}`;
  if (/^\+506\d{8}$/.test(phone)) return `+506 ${phone.slice(4, 8)}-${phone.slice(8)}`;
  return phone;
}
