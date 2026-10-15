import type { Schema } from "./client";
import { idempotencyKey, KnowledgeManagementClient } from "./client";

type Upload = Schema<"KnowledgeUploadView">;
type Signed = Schema<"KnowledgeSignedPart">;
export function hashFile(file: Blob, signal: AbortSignal): Promise<string> {
  return new Promise((resolve, reject) => {
    signal.throwIfAborted();
    const worker = new Worker(new URL("./hash.worker.ts", import.meta.url), {
      type: "module",
    });
    const stop = () => {
      worker.terminate();
      signal.removeEventListener("abort", abort);
    };
    const abort = () => {
      stop();
      reject(signal.reason ?? new DOMException("Aborted", "AbortError"));
    };
    signal.addEventListener("abort", abort, { once: true });
    worker.onmessage = ({
      data,
    }: MessageEvent<{ digest?: string; error?: string }>) => {
      stop();
      if (data.digest) resolve(data.digest);
      else reject(new Error(data.error ?? "FILE_HASH_FAILED"));
    };
    worker.onerror = () => {
      stop();
      reject(new Error("FILE_HASH_FAILED"));
    };
    worker.postMessage(file);
  });
}
export async function transferFile(
  client: KnowledgeManagementClient,
  file: File,
  identityScope: string,
  signal: AbortSignal,
  update: (
    upload: Upload | null,
    phase: "hashing" | "uploading",
    sent: number,
  ) => void,
): Promise<Upload> {
  update(null, "hashing", 0);
  const digest = await hashFile(file, signal);
  const relativePath = file.webkitRelativePath || file.name;
  const format = relativePath.split(".").at(-1)?.toUpperCase();
  if (
    !["DOC", "DOCX", "HTML", "PDF", "TXT", "XHTML", "RAR", "ZIP"].includes(
      format ?? "",
    )
  )
    throw new Error("UNSUPPORTED_KNOWLEDGE_FORMAT");
  // Only an opaque identity is retained. Signed URLs, secrets and file content never are.
  const resumeKey = `kb01:${identityScope}:${digest}:${relativePath}`;
  const prior = sessionStorage.getItem(resumeKey);
  let row = prior
    ? await client.get<Upload>(
        `/upload-sessions/${encodeURIComponent(prior)}`,
        signal,
      )
    : await client.mutate<Upload>("/upload-sessions", {
        relative_path: relativePath,
        declared_format: format,
        declared_bytes: file.size,
        content_sha256: digest,
        idempotency_key: idempotencyKey(),
      });
  if (
    row.content_sha256 !== digest ||
    row.declared_bytes !== file.size ||
    row.relative_path !== relativePath
  )
    throw new Error("UPLOAD_RESUME_IDENTITY_MISMATCH");
  sessionStorage.setItem(resumeKey, row.upload_session_id);
  if (row.status !== "UPLOADING") {
    update(row, "uploading", row.received_bytes ?? 0);
    return row;
  }
  const received = new Set(
    (row.received_parts ?? []).map((part) => part.part_number),
  );
  for (let number = 1; number <= row.part_count; number++) {
    signal.throwIfAborted();
    if (received.has(number)) continue;
    const part = file.slice(
      (number - 1) * row.part_bytes,
      Math.min(number * row.part_bytes, file.size),
    );
    const partDigest = await hashFile(part, signal);
    const signed = await client.mutate<Signed>(
      `/upload-sessions/${row.upload_session_id}/part-url`,
      { part_number: number, content_sha256: partDigest },
    );
    // Browser supplies Content-Length from the exact Blob; application credentials are omitted.
    const headers = Object.fromEntries(
      Object.entries(signed.headers).filter(
        ([key]) => key.toLowerCase() !== "content-length",
      ),
    );
    const response = await fetch(signed.url, {
      method: "PUT",
      body: part,
      headers,
      credentials: "omit",
      redirect: "error",
      signal,
    });
    if (!response.ok) throw new Error(`UPLOAD_PART_HTTP_${response.status}`);
    row = await client.mutate<Upload>(
      `/upload-sessions/${row.upload_session_id}/parts`,
      {
        part_number: number,
        content_sha256: partDigest,
        expected_record_version: row.record_version,
        idempotency_key: idempotencyKey(),
      },
    );
    update(
      row,
      "uploading",
      row.received_bytes ?? Math.min(number * row.part_bytes, file.size),
    );
  }
  row = await client.mutate<Upload>(
    `/upload-sessions/${row.upload_session_id}/complete`,
    {
      expected_record_version: row.record_version,
      idempotency_key: idempotencyKey(),
    },
  );
  update(row, "uploading", file.size);
  return row;
}
