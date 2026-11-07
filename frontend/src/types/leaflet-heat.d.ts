// leaflet.heat@1 ships declarations written for @types/leaflet@2 (generic Layer,
// MapListeners), which this app does not use (@types/leaflet@1.9), so they fail to
// resolve. Declare the small subset this app uses instead.
declare module "leaflet.heat" {
  import type { Layer, LayerOptions } from "leaflet";

  export interface HeatLayerOptions extends LayerOptions {
    radius?: number;
    blur?: number;
    maxZoom?: number;
    minOpacity?: number;
    max?: number;
    gradient?: Record<number, string>;
  }

  export class HeatLayer extends Layer {
    constructor(latlngs: Array<[number, number, number]>, options?: HeatLayerOptions);
  }
}
