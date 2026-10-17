import { describe, expect, it } from "vitest";
import { safeBrowserError } from "../../e2e/kb01-safe-evidence";

describe("KB01 public diagnostic evidence", () => {
  it("retains CORS failure identity without signer credentials or URL secrets", () => {
    const raw = "CORS denied https://fixture-user:fixture-password@localhost:19000/owned?X-Amz-Credential=fixture-key&X-Amz-Signature=fixture-signature#fixture-token";
    const safe = safeBrowserError(raw);
    expect(safe).toBe("CORS denied https://localhost:19000/owned?[REDACTED]#[REDACTED]");
    for (const value of ["fixture-user", "fixture-password", "fixture-key", "fixture-signature", "fixture-token"]) expect(safe).not.toContain(value);
  });
  it("does not suppress an unexpected failure or its HTTP status", () => {
    expect(safeBrowserError("HTTP_500 request https://localhost/owned?token=fixture"))
      .toBe("HTTP_500 request https://localhost/owned?[REDACTED]");
    expect(safeBrowserError("SCANNING_FAILED")).toBe("SCANNING_FAILED");
  });
});
