import 'leaflet/dist/leaflet.css';
import 'react-leaflet-cluster/dist/assets/MarkerCluster.css';
import 'react-leaflet-cluster/dist/assets/MarkerCluster.Default.css';

import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import L from 'leaflet';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';
import {
  useAnalyticsQuery,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
  Input,
  Badge,
  Skeleton,
} from '@databricks/appkit-ui/react';
import type { InferRowType } from '@databricks/appkit-ui/react';
import { useState, useMemo } from 'react';
import { MapPin, Globe, Phone, Search, BedDouble, Stethoscope } from 'lucide-react';

// Row shape from the facility_locations query (kept in sync with the
// auto-generated query registry). Arrow's toArray() is loosely typed, so we
// cast to this for type-safe field access.
type FacilityLocation = InferRowType<'facility_locations'>;

// Leaflet's default marker images don't resolve under a bundler (Vite). Its
// `_getIconUrl` re-prepends an auto-detected `imagePath` to the option value,
// which doubles the (already-absolute) Vite asset URL into a broken `src`.
// Deleting it makes Leaflet use the explicit imported URLs verbatim.
delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl;
L.Icon.Default.mergeOptions({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
});

const num = new Intl.NumberFormat('en-US');

function FacilityMap() {
  const [search, setSearch] = useState('');

  // ARROW_STREAM (binary, chunked) — the full ~10K-row payload exceeds the
  // analytics plugin's 1MB JSON-event limit, so the default JSON_ARRAY format
  // errors out. Arrow streams the result and returns a TypedArrowTable.
  const { data, loading, error } = useAnalyticsQuery('facility_locations', {}, { format: 'ARROW_STREAM' });

  // TypedArrowTable → plain row objects. We load the full dataset once and
  // filter in-memory: no per-keystroke refetch, and (unlike a server-side
  // search) a no-match search renders the empty state instead of an Arrow
  // "empty result" error.
  const rows = useMemo<FacilityLocation[]>(() => (data ? (data.toArray() as FacilityLocation[]) : []), [data]);
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((f) => f.name?.toLowerCase().includes(q) || f.city?.toLowerCase().includes(q));
  }, [rows, search]);

  return (
    <Card className="shadow-sm">
      <CardHeader className="gap-4">
        <div>
          <CardTitle>Facility locations</CardTitle>
          <CardDescription>
            {loading
              ? 'Loading facility coordinates…'
              : `Showing ${num.format(filtered.length)} of ${num.format(rows.length)} geocoded facilities · Virtue Foundation dataset`}
          </CardDescription>
        </div>
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search facility or city…"
            className="pl-9"
          />
        </div>
      </CardHeader>
      <CardContent>
        {error && (
          <div className="text-destructive bg-destructive/10 p-3 rounded-md mb-4">Error loading map: {error}</div>
        )}

        {loading && <Skeleton className="h-[70vh] w-full rounded-lg" />}

        {!loading && !error && filtered.length === 0 && (
          <p className="text-muted-foreground text-center py-10">
            No facilities match your search. Try a different name or city.
          </p>
        )}

        {!loading && !error && filtered.length > 0 && (
          <div className="h-[70vh] w-full overflow-hidden rounded-lg border">
            <MapContainer center={[20, 0]} zoom={2} scrollWheelZoom className="h-full w-full" worldCopyJump>
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <MarkerClusterGroup chunkedLoading>
                {filtered.map((f, i) => (
                  <Marker key={`${f.unique_id}-${i}`} position={[f.latitude, f.longitude]}>
                    <Popup>
                      <div className="space-y-1.5">
                        <div className="font-semibold text-foreground">{f.name}</div>
                        <div className="text-xs text-muted-foreground inline-flex items-center gap-1">
                          <MapPin className="h-3 w-3" /> {f.city}
                          {f.country ? `, ${f.country}` : ''}
                        </div>
                        <div className="flex gap-3 text-xs text-muted-foreground">
                          {f.doctors != null && (
                            <span className="inline-flex items-center gap-1">
                              <Stethoscope className="h-3 w-3" /> {num.format(Number(f.doctors))} doctors
                            </span>
                          )}
                          {f.beds != null && (
                            <span className="inline-flex items-center gap-1">
                              <BedDouble className="h-3 w-3" /> {num.format(Number(f.beds))} beds
                            </span>
                          )}
                        </div>
                        {f.phone && (
                          <div className="text-xs text-muted-foreground inline-flex items-center gap-1">
                            <Phone className="h-3 w-3" /> {f.phone}
                          </div>
                        )}
                        {f.website && (
                          <a
                            href={f.website.startsWith('http') ? f.website : `https://${f.website}`}
                            target="_blank"
                            rel="noreferrer"
                            className="text-xs text-primary hover:underline inline-flex items-center gap-1"
                          >
                            <Globe className="h-3 w-3" /> {f.website}
                          </a>
                        )}
                      </div>
                    </Popup>
                  </Marker>
                ))}
              </MarkerClusterGroup>
            </MapContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function MapPage() {
  return (
    <div className="max-w-7xl mx-auto px-4 md:px-6 py-8 space-y-8">
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary mt-0.5">
          <MapPin className="h-5 w-5" />
        </span>
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-bold text-foreground">Facility Map</h2>
            <Badge variant="secondary" className="font-normal">
              Virtue Foundation · DAIS 2026
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Every geocoded healthcare facility, plotted by latitude and longitude. Zoom in to break clusters into
            individual pins.
          </p>
        </div>
      </div>

      <FacilityMap />
    </div>
  );
}
