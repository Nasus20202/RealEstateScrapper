// frontend/src/features/settings/SettingsPage.tsx
import { useEffect, useState } from "react";

import { getSettings, updateSettings } from "../../api/client";
import type { SettingsOut } from "../../api/types";

export function SettingsPage() {
  const [settings, setSettings] = useState<SettingsOut | null>(null);
  const [interval, setIntervalValue] = useState("");
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
      enabled_source_ids: enabled,
    });
    setSettings(updated);
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
        <label htmlFor="set-interval">Interwał (min)</label>
        <input
          id="set-interval"
          inputMode="numeric"
          value={interval}
          onChange={(e) => setIntervalValue(e.target.value)}
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
