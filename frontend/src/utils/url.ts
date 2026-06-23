/**
 * Validate and sanitize a URL string.
 *
 * Only allows http:// and https:// protocols. All other protocols
 * (javascript:, data:, vbscript:, etc.) are rejected to prevent XSS.
 *
 * @param url - The URL string to validate
 * @returns The validated URL or null if unsafe
 */
export function sanitizeUrl(url: string | null): string | null {
  if (!url) return null

  const trimmed = url.trim()
  if (!trimmed) return null

  try {
    const parsed = new URL(trimmed)

    // Only allow http and https protocols
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return null
    }

    return trimmed
  } catch {
    // Invalid URL format — reject
    return null
  }
}
