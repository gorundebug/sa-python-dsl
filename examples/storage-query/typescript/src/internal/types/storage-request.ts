/** User-owned request shared by all seven callable examples. */
export interface StorageRequest {
  requestId: string;
  key: string;
  value: Uint8Array;
}
