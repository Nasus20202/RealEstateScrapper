// frontend/src/features/settings/SettingsPage.tsx
import { useEffect, useState } from "react";

import { cleanupDatabase, getSettings, updateSettings } from "../../api/client";
import type { SettingsOut } from "../../api/types";

export function SettingsPage() {
  const [settings, setSettings] = useState<SettingsOut | null>(null);
  const [interval, setIntervalValue] = useState("");
  const [schedulerEnabled, setSchedulerEnabled] = useState(false);
  const [cron, setCron] = useState("");
  const [defaultCities, setDefaultCities] = useState("");
  const [defaultMaxPages, setDefaultMaxPages] = useState("");
  const [enabled, setEnabled] = useState<string[]>([]);
  const [sourcePages, setSourcePages] = useState<Record<string, string>>({});
  const [sourceCrons, setSourceCrons] = useState<Record<string, string>>({});
  const [cleanupArmed, setCleanupArmed] = useState(false);
  const [cleanupMessage, setCleanupMessage] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    void (async () => {
      const data = await getSettings();
      setSettings(data);
      setIntervalValue(
        data.scheduler_interval_minutes == null ? "" : String(data.scheduler_interval_minutes),
      );
      setSchedulerEnabled(data.scheduler_enabled ?? false);
      setCron(data.scheduler_cron ?? "");
      setDefaultCities((data.default_cities ?? []).join(", "));
      setDefaultMaxPages(data.default_max_pages == null ? "" : String(data.default_max_pages));
      setEnabled(data.sources);
      setSourcePages(
        Object.fromEntries(
          data.sources.map((source) => [source, String(data.source_max_pages?.[source] ?? "")]),
        ),
      );
      setSourceCrons(
        Object.fromEntries(
          data.sources.map((source) => [source, data.source_crons?.[source] ?? ""]),
        ),
      );
    })();
  }, []);

  if (!settings) {
    return <p className="loading">Ładowanie…</p>;
  }

  function toggleSource(source: string) {
    setEnabled((prev) =>
      prev.includes(source) ? prev.filter((s) => s !== source) : [...prev, source],
    );
  }

  function updateSourcePages(source: string, value: string) {
    setSourcePages((prev) => ({ ...prev, [source]: value }));
  }

  function updateSourceCron(source: string, value: string) {
    setSourceCrons((prev) => ({ ...prev, [source]: value }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const parsed = Number(interval.trim());
    const updated = await updateSettings({
      scheduler_interval_minutes:
        interval.trim() === "" || Number.isNaN(parsed) ? undefined : parsed,
      scheduler_enabled: schedulerEnabled,
      scheduler_cron: cron.trim() || null,
      default_cities: defaultCities
        .split(",")
        .map((city) => city.trim())
        .filter(Boolean),
      default_max_pages: defaultMaxPages.trim() === "" ? 0 : Number(defaultMaxPages.trim()) || 0,
      enabled_source_ids: enabled,
      source_max_pages: Object.fromEntries(
        Object.entries(sourcePages)
          .map(([source, value]) => [source, Number(value.trim())] as const)
          .filter((entry) => !Number.isNaN(entry[1]) && entry[1] > 0),
      ),
      source_crons: Object.fromEntries(
        Object.entries(sourceCrons).filter(([, value]) => value.trim()),
      ),
    });
    setSettings(updated);
    setSchedulerEnabled(updated.scheduler_enabled ?? false);
    setCron(updated.scheduler_cron ?? "");
    setDefaultCities((updated.default_cities ?? []).join(", "));
    setDefaultMaxPages(updated.default_max_pages == null ? "" : String(updated.default_max_pages));
    setSourcePages(
      Object.fromEntries(
        updated.sources.map((source) => [source, String(updated.source_max_pages?.[source] ?? "")]),
      ),
    );
    setSourceCrons(
      Object.fromEntries(
        updated.sources.map((source) => [source, updated.source_crons?.[source] ?? ""]),
      ),
    );
    setSaved(true);
  }

  async function onCleanup() {
    if (!cleanupArmed) {
      setCleanupArmed(true);
      return;
    }
    const result = await cleanupDatabase();
    setCleanupMessage(`Usunięto ${result.deleted_listings} ofert.`);
    setCleanupArmed(false);
  }

  return (
    <section className="settings-page">
      <header className="settings-header">
        <div>
          <h2>Ustawienia</h2>
          <p>Konfiguracja LLM, schedulera i providerów scrapingu.</p>
        </div>
        <div className="settings-actions">
          <button type="submit" form="settings-form">
            Zapisz
          </button>
          {saved && <span className="saved">Zapisano</span>}
        </div>
      </header>
      <dl className="settings-info">
        <div>
          <dt>LLM</dt>
          <dd>{settings.llm_enabled ? "włączony" : "wyłączony"}</dd>
        </div>
        <div>
          <dt>Model</dt>
          <dd>{settings.llm_model ?? "—"}</dd>
        </div>
        <div>
          <dt>Embedding</dt>
          <dd>{settings.llm_embedding_model ?? "—"}</dd>
        </div>
        <div>
          <dt>Base URL</dt>
          <dd>{settings.llm_base_url}</dd>
        </div>
        <div>
          <dt>Klucz API</dt>
          <dd>{settings.llm_api_key_set ? "Klucz API: ustawiony" : "Klucz API: brak"}</dd>
        </div>
      </dl>

      <div className="settings-grid">
        <form id="settings-form" className="settings-form" onSubmit={onSubmit}>
          <section className="settings-card">
            <h3>Scheduler globalny</h3>
            <label className="settings-check" htmlFor="set-scheduler-enabled">
              <input
                id="set-scheduler-enabled"
                type="checkbox"
                checked={schedulerEnabled}
                onChange={(e) => setSchedulerEnabled(e.target.checked)}
              />
              Włącz cykliczny scraping
            </label>

            <label htmlFor="set-interval">Interwał (min)</label>
            <input
              id="set-interval"
              inputMode="numeric"
              value={interval}
              onChange={(e) => setIntervalValue(e.target.value)}
            />

            <label htmlFor="set-cron">Cron globalny</label>
            <input
              id="set-cron"
              value={cron}
              onChange={(e) => setCron(e.target.value)}
              placeholder="np. 15 */6 * * *"
            />
          </section>

          <section className="settings-card">
            <h3>Zakres scrapingu</h3>
            <label htmlFor="set-default-cities">Miasta domyślne</label>
            <input
              id="set-default-cities"
              value={defaultCities}
              onChange={(e) => setDefaultCities(e.target.value)}
              placeholder="Gdańsk, Gdynia, Sopot"
            />

            <label htmlFor="set-default-max-pages">Maks. stron (domyślnie)</label>
            <input
              id="set-default-max-pages"
              inputMode="numeric"
              value={defaultMaxPages}
              onChange={(e) => setDefaultMaxPages(e.target.value)}
              placeholder="puste = 1 strona"
            />

            <fieldset>
              <legend>Providerzy</legend>
              <div className="provider-settings">
                {settings.sources.map((source) => (
                  <div key={source} className="provider-settings__row">
                    <label className="settings-check" htmlFor={`src-${source}`}>
                      <input
                        id={`src-${source}`}
                        type="checkbox"
                        checked={enabled.includes(source)}
                        onChange={() => toggleSource(source)}
                      />
                      {source}
                    </label>
                    <label htmlFor={`set-pages-${source}`}>
                      Strony
                      <input
                        id={`set-pages-${source}`}
                        inputMode="numeric"
                        value={sourcePages[source] ?? ""}
                        onChange={(e) => updateSourcePages(source, e.target.value)}
                      />
                    </label>
                    <label htmlFor={`set-cron-${source}`}>
                      Cron providera
                      <input
                        id={`set-cron-${source}`}
                        value={sourceCrons[source] ?? ""}
                        onChange={(e) => updateSourceCron(source, e.target.value)}
                        placeholder={cron}
                      />
                    </label>
                  </div>
                ))}
              </div>
            </fieldset>
          </section>
        </form>

        <section className="settings-card danger-card">
          <h3>Cleanup bazy danych</h3>
          <p>
            Usuwa oferty, historię cen, analizy LLM i grupy duplikatów. Zapisane wyszukiwania,
            ulubione i konfiguracja zostają.
          </p>
          <button type="button" className="danger-button" onClick={() => void onCleanup()}>
            {cleanupArmed ? "Kliknij drugi raz, aby wyczyścić" : "Wyczyść bazę ofert"}
          </button>
          {cleanupArmed && (
            <button type="button" className="btn-ghost" onClick={() => setCleanupArmed(false)}>
              Anuluj
            </button>
          )}
          {cleanupMessage && <span className="saved">{cleanupMessage}</span>}
        </section>
      </div>
    </section>
  );
}
