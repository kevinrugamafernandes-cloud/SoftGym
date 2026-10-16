import { apiClient } from "@/lib/axios";
import { unwrapBlobError } from "@/lib/pdf";
import type {
  CollectionList, CollectionState, DashboardSummary, EnrollmentPayload, EnrollmentResult, GymSettings,
  GymSettingsUpdate, MonthlyCloseItem, MonthlyReport, SalesBook,
} from "@/types";

async function blob(url: string, params: Record<string, string | number>): Promise<Blob> {
  try {
    const { data } = await apiClient.get<Blob>(url, { params, responseType: "blob", timeout: 60_000 });
    return data;
  } catch (err) {
    return unwrapBlobError(err);
  }
}

export const settingsService = {
  get: async (signal?: AbortSignal): Promise<GymSettings> => (await apiClient.get<GymSettings>("/settings", { signal })).data,
  update: async (payload: GymSettingsUpdate): Promise<GymSettings> => (await apiClient.patch<GymSettings>("/settings", payload)).data,
};

export const enrollmentService = {
  /** Socio + primer cobro en UNA operación: si el cobro falla, el socio no se crea. */
  enroll: async (payload: EnrollmentPayload): Promise<EnrollmentResult> =>
    (await apiClient.post<EnrollmentResult>("/members/enroll", payload)).data,
};

export const collectionsService = {
  list: async (
    f: { state: CollectionState; search: string; page: number; size: number }, signal?: AbortSignal
  ): Promise<CollectionList> => {
    const search = f.search.trim();
    const { data } = await apiClient.get<CollectionList>("/collections", {
      params: { state: f.state, page: f.page, size: f.size, ...(search ? { search } : {}) },
      signal,
    });
    return data;
  },
  logReminder: async (memberId: string, kind: CollectionState): Promise<void> => {
    await apiClient.post(`/collections/${memberId}/reminders`, { kind });
  },
};

export const reportsService = {
  dashboard: async (signal?: AbortSignal): Promise<DashboardSummary> =>
    (await apiClient.get<DashboardSummary>("/dashboard", { signal })).data,
  salesBook: async (date_from: string, date_to: string, signal?: AbortSignal): Promise<SalesBook> =>
    (await apiClient.get<SalesBook>("/reports/sales-book", { params: { date_from, date_to }, signal, timeout: 60_000 })).data,
  monthly: async (year: number, month: number, signal?: AbortSignal): Promise<MonthlyReport> =>
    (await apiClient.get<MonthlyReport>("/reports/monthly", { params: { year, month }, signal })).data,
  closes: async (signal?: AbortSignal): Promise<MonthlyCloseItem[]> =>
    (await apiClient.get<MonthlyCloseItem[]>("/reports/monthly-closes", { signal })).data,
  closeMonth: async (year: number, month: number, notes: string | null): Promise<MonthlyReport> =>
    (await apiClient.post<MonthlyReport>("/reports/monthly-closes", { year, month, notes })).data,
  salesBookCsv: (date_from: string, date_to: string) => blob("/reports/sales-book.csv", { date_from, date_to }),
  monthlyPdf: (year: number, month: number) => blob("/reports/monthly.pdf", { year, month }),
};
