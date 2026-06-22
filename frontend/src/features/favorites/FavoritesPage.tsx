// frontend/src/features/favorites/FavoritesPage.tsx
import { useCallback, useEffect, useState } from "react";

import { getFavorites, getListing, removeFavorite } from "../../api/client";
import type { ListingDetailOut } from "../../api/types";
import { ListingCard } from "../listings/ListingCard";

export function FavoritesPage() {
  const [listings, setListings] = useState<ListingDetailOut[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const favorites = await getFavorites();
      const resolved = await Promise.all(favorites.map((fav) => getListing(fav.listing_id)));
      setListings(resolved);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onRemove(listingId: number) {
    await removeFavorite(listingId);
    setListings((prev) => prev.filter((l) => l.id !== listingId));
  }

  return (
    <section className="favorites-page">
      <h2>Ulubione</h2>
      {loading && <p className="loading">Ładowanie…</p>}
      {!loading && listings.length === 0 && <p>Brak ulubionych ofert.</p>}
      <div className="listings-grid">
        {listings.map((listing) => (
          <div key={listing.id} className="favorite-item">
            <ListingCard listing={listing} />
            <button type="button" onClick={() => void onRemove(listing.id)}>
              Usuń
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
