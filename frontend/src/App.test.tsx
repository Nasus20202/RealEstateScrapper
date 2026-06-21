// frontend/src/App.test.tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { App } from "./App";

describe("App", () => {
  it("renderuje nawigację i domyślną stronę listy ofert", async () => {
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
    // domyślna trasa renderuje formularz listy ofert (etykieta "Miasto")
    expect(await screen.findByLabelText("Miasto")).toBeInTheDocument();
  });

  it("renderuje stronę ustawień pod /settings", async () => {
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <App />
      </MemoryRouter>,
    );
    expect(await screen.findByText("Ustawienia")).toBeInTheDocument();
  });
});
