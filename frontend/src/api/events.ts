import { API_BASE } from "./client";
import type { ScrapeEvent } from "./types";

export function subscribeScrapeEvents(
  onEvent: (event: ScrapeEvent) => void,
): () => void {
  const source = new EventSource(`${API_BASE}/events`);
  const handler = (event: MessageEvent) => {
    try {
      onEvent(JSON.parse(event.data) as ScrapeEvent);
    } catch {
      // ignorujemy niepoprawne payloady
    }
  };
  source.addEventListener("scrape", handler as EventListener);
  return () => {
    source.removeEventListener("scrape", handler as EventListener);
    source.close();
  };
}
