// frontend/src/features/settings/SettingsPage.tsx
import { useEffect, useState } from "react";

import { getSettings, updateSettings } from "../../api/client";
import type { SettingsOut } from "../../api/types";

export function SettingsPage() {
  const [settings, setSettings] = useState<SettingsOut | null>(null);
  const [interval, setIntervalValue] = useState("");
  const [schedulerEnabled, setSchedulerEnabled] = useState(false);
  const [cron, setCron] = useState("");
  const [defaultCities, setDefaultCities] = useState("");
  const [enabled, setEnabled] = useState<string[]>([]);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    void (async () => {
      const data = await getSettings();
      setSettings(data);
      setIntervalValue(
        data.scheduler_interval_minutes == null
          ? ""
          : String(data.scheduler_interval_minutes),
      );
      setSchedulerEnabled(data.scheduler_enabled ?? false);
      setCron(data.scheduler_cron ?? "");
      setDefaultCities((data.default_cities ?? []).join(", "));
      setEnabled(data.sources);
    })();
  }, []);

  if (!settings) {
    return <p className="loading">Ładowanie…</p>;
  }

  function toggleSource(source: string) {
    setEnabled((prev) =>
      prev.includes(source)
        ? prev.filter((s) => s !== source)
        : [...prev, source],
    );
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
      enabled_source_ids: enabled,
    });
    setSettings(updated);
    setSchedulerEnabled(updated.scheduler_enabled ?? false);
    setCron(updated.scheduler_cron ?? "");
    setDefaultCities((updated.default_cities ?? []).join(", "));
    setSaved(true);
  }

  return (
    <section className="settings-page">
      <h2>Ustawienia</h2>
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
          <dt>Base URL</dt>
          <dd>{settings.llm_base_url}</dd>
        </div>
        <div>
          <dt>Klucz API</dt>
          <dd>{settings.llm_api_key_set ? "Klucz API: ustawiony" : "Klucz API: brak"}</dd>
        </div>
      </dl>

      <form onSubmit={onSubmit}>
        <label htmlFor="set-scheduler-enabled">Scheduler</label>
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

        <label htmlFor="set-cron">Cron</label>
        <input
          id="set-cron"
          value={cron}
          onChange={(e) => setCron(e.target.value)}
          placeholder="np. 15 */6 * * *"
        />

        <label htmlFor="set-default-cities">Miasta domyślne</label>
        <input
          id="set-default-cities"
          value={defaultCities}
          onChange={(e) => setDefaultCities(e.target.value)}
          placeholder="Gdańsk, Gdynia, Sopot"
        />

        <fieldset>
          <legend>Aktywne źródła</legend>
          {settings.sources.map((source) => (
            <label key={source} htmlFor={`src-${source}`}>
              <input
                id={`src-${source}`}
                type="checkbox"
                checked={enabled.includes(source)}
                onChange={() => toggleSource(source)}
              />
              {source}
            </label>
          ))}
        </fieldset>

        <button type="submit">Zapisz</button>
        {saved && <span className="saved">Zapisano</span>}
      </form>
    </section>
  );
}
