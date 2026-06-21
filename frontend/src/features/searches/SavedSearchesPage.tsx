// frontend/src/features/searches/SavedSearchesPage.tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { createSearch, deleteSearch, getSearches } from "../../api/client";
import type { SavedSearchOut } from "../../api/types";

function buildListingsSearch(search: SavedSearchOut): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(search.filters)) {
    if (Array.isArray(value)) {
      for (const item of value) params.append(key, String(item));
    } else if (value != null) {
      params.set(key, String(value));
    }
  }
  if (search.nl_query) params.set("q", search.nl_query);
  return params.toString();
}

export function SavedSearchesPage() {
  const navigate = useNavigate();
  const [searches, setSearches] = useState<SavedSearchOut[]>([]);
  const [name, setName] = useState("");
  const [nlQuery, setNlQuery] = useState("");

  async function load() {
    setSearches(await getSearches());
  }

  useEffect(() => {
    void load();
  }, []);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    await createSearch({
      name: name.trim(),
      filters: {},
      nl_query: nlQuery.trim() || null,
    });
    setName("");
    setNlQuery("");
    await load();
  }

  async function onDelete(id: number) {
    await deleteSearch(id);
    await load();
  }

  function apply(search: SavedSearchOut) {
    navigate(`/?${buildListingsSearch(search)}`);
  }

  return (
    <section className="searches-page">
      <h2>Zapisane wyszukiwania</h2>
      <ul className="searches-list">
        {searches.map((search) => (
          <li key={search.id}>
            <span className="searches-list__name">{search.name}</span>
            {search.nl_query ? ` — ${search.nl_query}` : ""}
            <button type="button" onClick={() => apply(search)}>
              Zastosuj
            </button>
            <button type="button" onClick={() => void onDelete(search.id)}>
              Usuń
            </button>
          </li>
        ))}
      </ul>

      <form onSubmit={onCreate}>
        <label htmlFor="search-name">Nazwa</label>
        <input
          id="search-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <label htmlFor="search-nl">Zapytanie NL</label>
        <input
          id="search-nl"
          value={nlQuery}
          onChange={(e) => setNlQuery(e.target.value)}
        />
        <button type="submit">Zapisz wyszukiwanie</button>
      </form>
    </section>
  );
}
