import { useCallback, useEffect, useState } from "react";

import { getRuns, postScrape } from "../../api/client";
import { subscribeScrapeEvents } from "../../api/events";
import type { ScrapeEvent, ScrapeRequest, ScrapeRunOut } from "../../api/types";

function toNumber(value: string): number | undefined {
  const trimmed = value.trim();
  if (trimmed === "") return undefined;
  const parsed = Number(trimmed);
  return Number.isNaN(parsed) ? undefined : parsed;
}

export function ScrapePage() {
  const [city, setCity] = useState("");
  const [maxPages, setMaxPages] = useState("1");
  const [sources, setSources] = useState("");
  const [runs, setRuns] = useState<ScrapeRunOut[]>([]);
  const [events, setEvents] = useState<ScrapeEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadRuns = useCallback(async () => {
    setRuns(await getRuns());
  }, []);

  useEffect(() => {
    void loadRuns();
  }, [loadRuns]);

  useEffect(() => {
    const unsubscribe = subscribeScrapeEvents((event) => {
      setEvents((prev) => [...prev, event]);
    });
    return unsubscribe;
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (city.trim() === "") {
      setError("Miasto jest wymagane");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const sourceIds = sources
        .split(",")
        .map((s) => s.trim())
        .filter((s) => s.length > 0);
      const body: ScrapeRequest = {
        city: city.trim(),
        max_pages: toNumber(maxPages) ?? 1,
      };
      if (sourceIds.length > 0) body.source_ids = sourceIds;
      await postScrape(body);
      await loadRuns();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Błąd scrapingu");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="scrape-page">
      <form className="scrape-form" onSubmit={onSubmit}>
        <label htmlFor="s-city">Miasto</label>
        <input id="s-city" value={city} onChange={(e) => setCity(e.target.value)} />

        <label htmlFor="s-pages">Maks. stron</label>
        <input
          id="s-pages"
          inputMode="numeric"
          value={maxPages}
          onChange={(e) => setMaxPages(e.target.value)}
        />

        <label htmlFor="s-sources">Źródła (przecinki)</label>
        <input
          id="s-sources"
          value={sources}
          onChange={(e) => setSources(e.target.value)}
        />

        <button type="submit" disabled={busy}>
          Uruchom scraping
        </button>
      </form>
      {error && <p className="error">{error}</p>}

      <section className="scrape-progress">
        <h3>Postęp na żywo</h3>
        {events.length === 0 ? (
          <p>Brak zdarzeń.</p>
        ) : (
          <ul>
            {events.map((event, index) => (
              <li key={index}>
                {event.source_id} — {event.status} (nowe {event.new}, akt.{" "}
                {event.updated})
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="scrape-runs">
        <h3>Ostatnie przebiegi</h3>
        <ul>
          {runs.map((r) => (
            <li key={r.id}>
              {r.source_id} — {r.status} — nowe: {r.new_count}, akt.:{" "}
              {r.updated_count}, usun.: {r.gone_count}
              {r.error_message ? ` — błąd: ${r.error_message}` : ""}
            </li>
          ))}
        </ul>
      </section>
    </section>
  );
}
