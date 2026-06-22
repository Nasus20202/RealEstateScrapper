import "leaflet";

declare module "leaflet" {
  export function heatLayer(
    latlngs: Array<[number, number, number]>,
    options?: {
      radius?: number;
      blur?: number;
      maxZoom?: number;
      minOpacity?: number;
      gradient?: Record<number, string>;
    },
  ): Layer;
}

declare module "leaflet.heat";
