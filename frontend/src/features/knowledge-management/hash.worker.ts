import { digestStream } from "./streamDigest";

// A dedicated Worker owns incremental state; no whole-file ArrayBuffer is created.
self.onmessage = async ({ data }: MessageEvent<Blob>) => {
  try {
    self.postMessage({ digest: await digestStream(data.stream()) });
  } catch {
    self.postMessage({ error: "FILE_HASH_FAILED" });
  }
};
