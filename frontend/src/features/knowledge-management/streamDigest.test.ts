import { it, expect } from "vitest";
import { ReadableStream } from "node:stream/web";
import { digestStream } from "./streamDigest";

it("hashes differently segmented raw bytes to the same published SHA-256 vector", async () => {
  for (const parts of [["abc"], ["a", "b", "c"], ["ab", "", "c"]]) {
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const part of parts)
          controller.enqueue(new TextEncoder().encode(part));
        controller.close();
      },
    });
    expect(
      await digestStream(stream as globalThis.ReadableStream<Uint8Array>),
    ).toBe("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  }
});
it("handles a long stream without requesting a whole-file buffer", async () => {
  let sent = 0;
  const stream = new ReadableStream<Uint8Array>({
    pull(controller) {
      if (sent === 1000) {
        controller.close();
        return;
      }
      sent++;
      controller.enqueue(new Uint8Array(1000).fill(97));
    },
  });
  expect(
    await digestStream(stream as globalThis.ReadableStream<Uint8Array>),
  ).toBe("cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0");
  expect(sent).toBe(1000);
});
