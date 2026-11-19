/** Successful completion is an application result, not a special port. */
export interface StorageResult {
  requestId: string;
  kind: "record" | "command" | "object" | "page" | "completed";
  value: Uint8Array;
}
