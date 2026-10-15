import type { components } from "../../api/kb01-generated";
import { AdminClient } from "../admin/client";
export type Schema<K extends keyof components["schemas"]> =
  components["schemas"][K];
export const managementPath = "/admin/knowledge-management";
export class KnowledgeManagementClient {
  constructor(readonly admin: AdminClient) {}
  get<T>(path: string, signal?: AbortSignal) {
    return this.admin.request<T>(
      managementPath + path,
      "GET",
      undefined,
      signal,
    );
  }
  mutate<T>(path: string, body: unknown, method = "POST") {
    return this.admin.request<T>(managementPath + path, method, body);
  }
}
export const idempotencyKey = () => crypto.randomUUID();
export const mutation = (version: number, reason: string) => ({
  expected_record_version: version,
  reason,
  idempotency_key: idempotencyKey(),
});
