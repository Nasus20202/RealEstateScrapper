import { useCallback, useEffect, useState } from "react";

import { getRuns, getSettings, postScrape } from "../../api/client";
import { subscribeScrapeEvents } from "../../api/events";
import type { ScrapeEvent, ScrapeRequest, ScrapeRunOut } from "../../api/types";

function toNumber(value: string): number | undefined {
  const trimmed = value.trim();
  if (trimmed === "") return undefined;
  const parsed = Number(trimmed);
  return Number.isNaN(parsed) ? undefined : parsed;
}

function formatDt(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pl-PL", { dateStyle: "short", timeStyle: "short" });
}

const STATUS_CLASS: Record<string, string> = {
  done: "run-status--done",
  running: "run-status--running",
  error: "run-status--error",
};

export function ScrapePage() {
  const [city, setCity] = useState("Gdańsk");
  const [maxPages, setMaxPages] = useState("1");
  const [availableSources, setAvailableSources] = useState<string[]>([]);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [runs, setRuns] = useState<ScrapeRunOut[]>([]);
  const [events, setEvents] = useState<ScrapeEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadRuns = useCallback(async () => {
    setRuns(await getRuns());
  }, []);

  useEffect(() => {
    void loadRuns();
    void getSettings().then((s) => setAvailableSources(s.sources)).catch(() => {});
  }, [loadRuns]);

  useEffect(() => {
    const unsubscribe = subscribeScrapeEvents((event) => {
      setEvents((prev) => [event, ...prev].slice(0, 50));
    });
    return unsubscribe;
  }, []);

  function toggleSource(id: string) {
    setSelectedSources((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id],
    );
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (city.trim() === "") {
      setError("Miasto jest wymagane");
      return;
    }
    setBusy(true);
    setError(null);
    setEvents([]);
    try {
      const body: ScrapeRequest = {
        city: city.trim(),
        max_pages: toNumber(maxPages) ?? 1,
      };
      if (selectedSources.length > 0) body.source_ids = selectedSources;
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
      <div className="scrape-layout">
        <div className="scrape-form-wrapper">
          <h2 className="scrape-section-title">Uruchom scraping</h2>
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

            {availableSources.length > 0 && (
              <>
                <label className="sources-label">Źródła</label>
                <div className="sources-checkboxes">
                  {availableSources.map((src) => (
                    <label key={src} className="source-check">
                      <input
                        type="checkbox"
                        checked={selectedSources.includes(src)}
                        onChange={() => toggleSource(src)}
                      />
                      {src}
                    </label>
                  ))}
                  <span className="sources-hint">
                    {selectedSources.length === 0 ? "wszystkie" : `${selectedSources.length} wybranych`}
                  </span>
                </div>
              </>
            )}

            <button type="submit" disabled={busy}>
              {busy ? "Trwa…" : "Uruchom"}
            </button>
          </form>
          {error && <p className="error">{error}</p>}
        </div>

        <div className="scrape-live">
          <h2 className="scrape-section-title">Postęp na żywo</h2>
          {events.length === 0 ? (
            <p className="scrape-empty">Uruchom scraping, aby zobaczyć postęp.</p>
          ) : (
            <ul className="scrape-events">
              {events.map((event, index) => (
                <li key={index} className={`scrape-event scrape-event--${event.status}`}>
                  <span className="scrape-event__source">{event.source_id}</span>
                  <span className="scrape-event__status">{event.status}</span>
                  <span className="scrape-event__counts">
                    +{event.new} nowych · {event.updated} akt. · {event.gone} usun.
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <section className="scrape-runs-section">
        <h2 className="scrape-section-title">Ostatnie przebiegi</h2>
        {runs.length === 0 ? (
          <p className="scrape-empty">Brak przebiegów.</p>
        ) : (
          <div className="runs-table">
            <div className="runs-table__head">
              <span>Źródło</span>
              <span>Status</span>
              <span>Nowe</span>
              <span>Akt.</span>
              <span>Usun.</span>
              <span>Czas</span>
            </div>
            {runs.map((r) => (
              <div key={r.id} className="runs-table__row">
                <span className="run-source">{r.source_id}</span>
                <span className={`run-status ${STATUS_CLASS[r.status] ?? ""}`}>{r.status}</span>
                <span className="run-num run-num--new">+{r.new_count}</span>
                <span className="run-num">~{r.updated_count}</span>
                <span className="run-num run-num--gone">{r.gone_count}</span>
                <span className="run-time">{formatDt(r.started_at)}</span>
                {r.error_message && (
                  <span className="run-error">{r.error_message}</span>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </section>
  );
}
