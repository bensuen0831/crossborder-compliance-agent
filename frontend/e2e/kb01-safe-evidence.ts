/** Preserve every diagnostic/error while excluding signed URLs from reports. */
export function safeBrowserError(text: string): string {
  return text.replace(/https?:\/\/[^\s"'<>]+/g, (value) => {
    try {
      const url = new URL(value);
      return url.origin + url.pathname + (url.search ? "?[REDACTED]" : "") +
        (url.hash ? "#[REDACTED]" : "");
    } catch {
      return "[REDACTED_URL]";
    }
  });
}
