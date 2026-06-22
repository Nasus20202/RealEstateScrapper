// frontend/src/features/favorites/FavoritesPage.tsx
import { useEffect, useState, useTransition } from "react";

import { getFavorites, getListing, removeFavorite } from "../../api/client";
import type { ListingDetailOut } from "../../api/types";
import { ListingCard } from "../listings/ListingCard";

export function FavoritesPage() {
  const [listings, setListings] = useState<ListingDetailOut[]>([]);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    startTransition(async () => {
      const favs = await getFavorites();
      const resolved = await Promise.all(favs.map((fav) => getListing(fav.listing_id)));
      setListings(resolved);
    });
  }, []);

  async function onRemove(listingId: number) {
    await removeFavorite(listingId);
    setListings((prev) => prev.filter((l) => l.id !== listingId));
  }

  if (isPending) {
    return (
      <section className="favorites-page">
        <h2>Ulubione</h2>
        <p className="loading">Ładowanie…</p>
      </section>
    );
  }

  return (
    <section className="favorites-page">
      <h2>Ulubione</h2>
      {listings.length === 0 && <p>Brak ulubionych ofert.</p>}
      <div className="listings-grid">
        {listings.map((listing) => (
          <div key={listing.id} className="favorite-item">
            <ListingCard listing={listing} />
            <button
              type="button"
              className="favorite-item__remove btn-ghost btn-sm"
              onClick={() => void onRemove(listing.id)}
            >
              Usuń
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
