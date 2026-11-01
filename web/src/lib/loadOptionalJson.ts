/** Optional exported bundles may be absent from an otherwise valid episode. */
export async function loadOptionalJson<T>(url: string): Promise<T | null> {
  const response = await fetch(url);
  if (!response.ok || !response.headers.get("content-type")?.includes("application/json")) return null;
  return response.json() as Promise<T>;
}
