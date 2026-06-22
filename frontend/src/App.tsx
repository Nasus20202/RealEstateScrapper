// frontend/src/App.tsx
import { NavLink, Route, Routes } from "react-router-dom";

import { FavoritesPage } from "./features/favorites/FavoritesPage";
import { ListingDetailPage } from "./features/listings/ListingDetailPage";
import { ListingsMapPage } from "./features/listings/ListingsMapPage";
import { ListingsPage } from "./features/listings/ListingsPage";
import { ScrapePage } from "./features/scrape/ScrapePage";
import { SavedSearchesPage } from "./features/searches/SavedSearchesPage";
import { SettingsPage } from "./features/settings/SettingsPage";

export function App() {
  return (
    <div className="app">
      <nav className="app-nav">
        <NavLink to="/" end className="app-nav__brand">
          <span className="app-nav__logo">◈</span>
          Trójmiasto&nbsp;Estate
        </NavLink>
        <NavLink to="/" end>
          Oferty
        </NavLink>
        <NavLink to="/mapa">Mapa</NavLink>
        <NavLink to="/scrape">Scraping</NavLink>
        <NavLink to="/searches">Zapisane</NavLink>
        <NavLink to="/favorites">Ulubione</NavLink>
        <NavLink to="/settings">Ustawienia</NavLink>
      </nav>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<ListingsPage />} />
          <Route path="/mapa" element={<ListingsMapPage />} />
          <Route path="/listings/:id" element={<ListingDetailPage />} />
          <Route path="/scrape" element={<ScrapePage />} />
          <Route path="/searches" element={<SavedSearchesPage />} />
          <Route path="/favorites" element={<FavoritesPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}
