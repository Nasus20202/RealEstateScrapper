import { API_BASE } from "./client";
import type { ScrapeEvent, ScrapeLogEvent } from "./types";

export function subscribeScrapeEvents(
  onEvent: (event: ScrapeEvent | ScrapeLogEvent) => void,
): () => void {
  const source = new EventSource(`${API_BASE}/events`);
  const handler = (event: MessageEvent) => {
    try {
      onEvent(JSON.parse(event.data) as ScrapeEvent | ScrapeLogEvent);
    } catch {
      // ignorujemy niepoprawne payloady
    }
  };
  source.addEventListener("scrape", handler as EventListener);
  source.addEventListener("scrape_log", handler as EventListener);
  return () => {
    source.removeEventListener("scrape", handler as EventListener);
    source.removeEventListener("scrape_log", handler as EventListener);
    source.close();
  };
}
