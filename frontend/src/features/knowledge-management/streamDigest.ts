import { sha256 } from "@noble/hashes/sha2.js";

/** Hash raw bytes incrementally; at most the current stream chunk is retained. */
export async function digestStream(
  stream: ReadableStream<Uint8Array>,
): Promise<string> {
  const reader = stream.getReader();
  const digest = sha256.create();
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      digest.update(value);
    }
    return Array.from(digest.digest(), (b) =>
      b.toString(16).padStart(2, "0"),
    ).join("");
  } finally {
    reader.releaseLock();
  }
}
