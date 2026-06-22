import { useCallback, useEffect, useState, useTransition } from "react";

import { getRuns, getSettings, postScrape } from "../../api/client";
import { subscribeScrapeEvents } from "../../api/events";
import type {
  ScrapeEvent,
  ScrapeLogEvent,
  ScrapeRequest,
  ScrapeRunOut,
  SettingsOut,
} from "../../api/types";

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

function isScrapeLogEvent(event: ScrapeEvent | ScrapeLogEvent): event is ScrapeLogEvent {
  return event.type === "scrape_log";
}

export function ScrapePage() {
  const [runs, setRuns] = useState<ScrapeRunOut[]>([]);
  const [settings, setSettings] = useState<SettingsOut | null>(null);
  const [events, setEvents] = useState<ScrapeEvent[]>([]);
  const [logs, setLogs] = useState<ScrapeLogEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const [cityMode, setCityMode] = useState("__default");
  const [customCity, setCustomCity] = useState("");
  const [maxPages, setMaxPages] = useState("1");
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [sourcePages, setSourcePages] = useState<Record<string, string>>({});

  useEffect(() => {
    startTransition(async () => {
      const [initialRuns, initialSettings] = await Promise.all([getRuns(), getSettings()]);
      setRuns(initialRuns);
      setSettings(initialSettings);
      setSourcePages(
        Object.fromEntries(
          initialSettings.sources.map((source) => [
            source,
            String(initialSettings.source_max_pages?.[source] ?? 1),
          ]),
        ),
      );
    });
  }, []);

  useEffect(() => {
    const unsubscribe = subscribeScrapeEvents((event) => {
      if (isScrapeLogEvent(event)) {
        setLogs((prev) => [event, ...prev].slice(0, 200));
      } else {
        setEvents((prev) => [event, ...prev].slice(0, 50));
      }
    });
    return unsubscribe;
  }, []);

  const loadRuns = useCallback(async () => {
    setRuns(await getRuns());
  }, []);

  if (isPending || !settings) {
    return (
      <section className="scrape-page">
        <p className="scrape-empty">Ładowanie…</p>
      </section>
    );
  }

  const availableSources = settings.sources;
  const defaultCities = settings.default_cities ?? [];

  function toggleSource(id: string) {
    setSelectedSources((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id],
    );
  }

  function updateSourcePages(source: string, value: string) {
    setSourcePages((prev) => ({ ...prev, [source]: value }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setEvents([]);
    setLogs([{ type: "scrape_log", source_id: "app", message: "Startuję scraping…" }]);
    try {
      const body: ScrapeRequest = {
        max_pages: toNumber(maxPages) ?? 1,
      };
      if (cityMode === "__custom" && customCity.trim()) {
        body.city = customCity.trim();
      } else if (cityMode !== "__default") {
        body.city = cityMode;
      }
      if (selectedSources.length > 0) body.source_ids = selectedSources;
      const providerPages = Object.fromEntries(
        Object.entries(sourcePages)
          .map(([source, value]) => [source, toNumber(value)] as const)
          .filter((entry): entry is [string, number] => entry[1] != null),
      );
      if (Object.keys(providerPages).length > 0) {
        body.source_max_pages = providerPages;
      }
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
            <label htmlFor="s-city-mode">Miasto</label>
            <select id="s-city-mode" value={cityMode} onChange={(e) => setCityMode(e.target.value)}>
              <option value="__default">
                Całe Trójmiasto ({defaultCities.join(", ") || "miasta domyślne"})
              </option>
              {defaultCities.map((defaultCity) => (
                <option key={defaultCity} value={defaultCity}>
                  {defaultCity}
                </option>
              ))}
              <option value="__custom">Własne miasto…</option>
            </select>

            {cityMode === "__custom" && (
              <>
                <label htmlFor="s-custom-city">Własne miasto</label>
                <input
                  id="s-custom-city"
                  value={customCity}
                  onChange={(e) => setCustomCity(e.target.value)}
                  placeholder="np. Rumia"
                />
              </>
            )}

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
                    <div key={src} className="source-config-row">
                      <label className="source-check">
                        <input
                          type="checkbox"
                          checked={selectedSources.includes(src)}
                          onChange={() => toggleSource(src)}
                        />
                        {src}
                      </label>
                      <label htmlFor={`s-pages-${src}`} className="source-pages-label">
                        Strony
                        <input
                          id={`s-pages-${src}`}
                          inputMode="numeric"
                          value={sourcePages[src] ?? "1"}
                          onChange={(e) => updateSourcePages(src, e.target.value)}
                        />
                      </label>
                    </div>
                  ))}
                  <span className="sources-hint">
                    {selectedSources.length === 0
                      ? "wszystkie; strony można ustawić osobno per provider"
                      : `${selectedSources.length} wybranych`}
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

          <h2 className="scrape-section-title scrape-section-title--logs">Logi scrapingu</h2>
          {logs.length === 0 ? (
            <p className="scrape-empty">Logi pojawią się po uruchomieniu scrapingu.</p>
          ) : (
            <ul className="scrape-logs">
              {logs.map((log, index) => (
                <li key={index} className="scrape-log">
                  <span className="scrape-log__source">{log.source_id}</span>
                  <span>{log.message}</span>
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
                {r.error_message && <span className="run-error">{r.error_message}</span>}
              </div>
            ))}
          </div>
        )}
      </section>
    </section>
  );
}
