// frontend/src/features/settings/SettingsPage.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { SettingsPage } from "./SettingsPage";
import { server } from "../../test/server";

const BASE = "/api";

function settings(overrides: Record<string, unknown> = {}) {
  return {
    llm_enabled: true,
    llm_base_url: "https://openrouter.ai/api/v1",
    llm_model: "anthropic/claude",
    llm_embedding_model: "text-embed",
    llm_api_key_set: true,
    scheduler_interval_minutes: 60,
    scheduler_enabled: false,
    scheduler_cron: null,
    default_cities: ["Gdańsk", "Gdynia", "Sopot"],
    sources: ["otodom", "olx"],
    source_max_pages: {},
    source_crons: {},
    ...overrides,
  };
}

describe("SettingsPage", () => {
  it("shows key status as boolean, never raw key", async () => {
    server.use(http.get(`${BASE}/settings`, () => HttpResponse.json(settings())));
    render(<SettingsPage />);
    expect(await screen.findByText("Klucz API: ustawiony")).toBeInTheDocument();
    expect(screen.getByText(/anthropic\/claude/)).toBeInTheDocument();
    // no password/key field present
    expect(document.querySelector('input[type="password"]')).toBeNull();
  });

  it("PUT saves interval and enabled sources", async () => {
    let body: unknown = null;
    server.use(
      http.get(`${BASE}/settings`, () =>
        HttpResponse.json(settings({ scheduler_interval_minutes: 60 })),
      ),
      http.put(`${BASE}/settings`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(settings());
      }),
    );
    render(<SettingsPage />);
    await screen.findByText("Klucz API: ustawiony");

    await userEvent.clear(screen.getByLabelText("Interwał (min)"));
    await userEvent.type(screen.getByLabelText("Interwał (min)"), "120");
    await userEvent.click(screen.getByLabelText("olx")); // disable olx
    await userEvent.click(screen.getByRole("button", { name: "Zapisz" }));

    await waitFor(() =>
      expect(body).toEqual({
        scheduler_interval_minutes: 120,
        scheduler_enabled: false,
        scheduler_cron: null,
        default_cities: ["Gdańsk", "Gdynia", "Sopot"],
        enabled_source_ids: ["otodom"],
        source_max_pages: { otodom: 1, olx: 1 },
        source_crons: {},
      }),
    );
  });
});
