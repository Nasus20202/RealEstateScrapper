// frontend/src/App.test.tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { App } from "./App";

describe("App", () => {
  it("renders navigation and default listings page", async () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Oferty" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Scraping" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Zapisane" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ulubione" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ustawienia" })).toBeInTheDocument();
    // default route renders listings form (label "Miasto")
    expect(await screen.findByLabelText("Miasto")).toBeInTheDocument();
  });

  it("renders settings page at /settings", async () => {
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <App />
      </MemoryRouter>,
    );
    expect(await screen.findByText("Ustawienia")).toBeInTheDocument();
  });

  it("redirects unknown paths to /", async () => {
    render(
      <MemoryRouter initialEntries={["/xyz"]}>
        <App />
      </MemoryRouter>,
    );
    expect(await screen.findByLabelText("Miasto")).toBeInTheDocument();
  });
});
