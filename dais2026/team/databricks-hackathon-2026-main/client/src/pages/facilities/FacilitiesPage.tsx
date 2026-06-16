import {
  useAnalyticsQuery,
  BarChart,
  DonutChart,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
  Input,
  Button,
  Badge,
  Skeleton,
} from '@databricks/appkit-ui/react';
import { sql } from '@databricks/appkit-ui/js';
import { useState, useEffect } from 'react';
import { Building2, MapPin, Stethoscope, BedDouble, Globe, Phone, Mail, Search, Activity } from 'lucide-react';
import type { ComponentType } from 'react';

const num = new Intl.NumberFormat('en-US');

// Specialty names arrive camelCase from the source JSON (e.g. "internalMedicine").
const prettySpecialty = (s: string) =>
  s
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (c) => c.toUpperCase())
    .trim();

interface KpiProps {
  label: string;
  value: string;
  icon: ComponentType<{ className?: string }>;
}

function KpiCard({ label, value, icon: Icon }: KpiProps) {
  return (
    <Card className="shadow-sm">
      <CardContent className="flex items-center gap-4 py-5">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Icon className="h-5 w-5" />
        </span>
        <div className="min-w-0">
          <div className="text-2xl font-bold text-foreground truncate">{value}</div>
          <div className="text-xs text-muted-foreground">{label}</div>
        </div>
      </CardContent>
    </Card>
  );
}

function KpiRow() {
  const { data, loading, error } = useAnalyticsQuery('facility_kpis', {});

  if (loading) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={`kpi-skel-${i}`} className="h-20 w-full rounded-xl" />
        ))}
      </div>
    );
  }
  if (error) {
    return <div className="text-destructive bg-destructive/10 p-3 rounded-md">Error loading metrics: {error}</div>;
  }
  const k = data?.[0];
  if (!k) return null;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
      <KpiCard label="Facilities" value={num.format(Number(k.total_facilities))} icon={Building2} />
      <KpiCard label="Cities" value={num.format(Number(k.cities))} icon={MapPin} />
      <KpiCard label="Avg. doctors" value={num.format(Number(k.avg_doctors))} icon={Stethoscope} />
      <KpiCard label="Total beds" value={num.format(Number(k.total_beds))} icon={BedDouble} />
      <KpiCard label="Have a website" value={`${Number(k.pct_online)}%`} icon={Globe} />
    </div>
  );
}

function SpecialtyBars() {
  const { data, loading, error } = useAnalyticsQuery('facilities_by_specialty', {});

  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 8 }, (_, i) => (
          <Skeleton key={`spec-skel-${i}`} className="h-7 w-full rounded" />
        ))}
      </div>
    );
  }
  if (error) {
    return <div className="text-destructive bg-destructive/10 p-3 rounded-md">Error: {error}</div>;
  }
  if (!data?.length) return null;

  const max = Math.max(...data.map((d) => Number(d.facilities)));

  return (
    <div className="space-y-2.5">
      {data.map((d) => {
        const value = Number(d.facilities);
        return (
          <div key={d.specialty} className="grid grid-cols-[10rem_1fr_auto] items-center gap-3">
            <span className="text-sm text-foreground truncate" title={prettySpecialty(d.specialty)}>
              {prettySpecialty(d.specialty)}
            </span>
            <div className="h-2.5 rounded-full bg-muted overflow-hidden">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${Math.max(2, (value / max) * 100)}%` }}
              />
            </div>
            <span className="text-xs tabular-nums text-muted-foreground w-14 text-right">{num.format(value)}</span>
          </div>
        );
      })}
    </div>
  );
}

const BED_FILTERS = [
  { label: 'Any size', value: 0 },
  { label: '100+ beds', value: 100 },
  { label: '300+ beds', value: 300 },
  { label: '500+ beds', value: 500 },
];

function Directory() {
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [minBeds, setMinBeds] = useState(0);

  // Debounce the search box so we don't fire a query on every keystroke.
  useEffect(() => {
    const t = setTimeout(() => setSearch(searchInput.trim()), 300);
    return () => clearTimeout(t);
  }, [searchInput]);

  const { data, loading, error } = useAnalyticsQuery('facilities_directory', {
    search: sql.string(search),
    min_beds: sql.number(minBeds),
  });

  return (
    <Card className="shadow-sm">
      <CardHeader className="gap-4">
        <div>
          <CardTitle>Facility directory</CardTitle>
          <CardDescription>
            Search {num.format(10088)} facilities by name or city. Showing up to 100 matches, largest first.
          </CardDescription>
        </div>
        <div className="flex flex-col sm:flex-row gap-3 sm:items-center">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search facility or city…"
              className="pl-9"
            />
          </div>
          <div className="flex gap-1.5 flex-wrap">
            {BED_FILTERS.map((f) => (
              <Button
                key={f.value}
                size="sm"
                variant={minBeds === f.value ? 'default' : 'outline'}
                onClick={() => setMinBeds(f.value)}
              >
                {f.label}
              </Button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {error && <div className="text-destructive bg-destructive/10 p-3 rounded-md mb-4">Error: {error}</div>}

        {loading && (
          <div className="space-y-2">
            {Array.from({ length: 6 }, (_, i) => (
              <Skeleton key={`row-skel-${i}`} className="h-12 w-full rounded" />
            ))}
          </div>
        )}

        {!loading && !error && data?.length === 0 && (
          <p className="text-muted-foreground text-center py-10">
            No facilities match your search. Try a different name or city.
          </p>
        )}

        {!loading && !error && !!data?.length && (
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-2.5 font-medium">Facility</th>
                  <th className="px-4 py-2.5 font-medium">City</th>
                  <th className="px-4 py-2.5 font-medium text-right">Doctors</th>
                  <th className="px-4 py-2.5 font-medium text-right">Beds</th>
                  <th className="px-4 py-2.5 font-medium">Contact</th>
                </tr>
              </thead>
              <tbody>
                {data.map((f, i) => (
                  <tr
                    key={`${f.unique_id}-${i}`}
                    className="border-b last:border-0 hover:bg-muted/40 transition-colors"
                  >
                    <td className="px-4 py-2.5">
                      <div className="font-medium text-foreground">{f.name}</div>
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
                    </td>
                    <td className="px-4 py-2.5 text-muted-foreground">{f.city}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">
                      {f.doctors != null ? num.format(Number(f.doctors)) : '—'}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums">
                      {f.beds != null ? num.format(Number(f.beds)) : '—'}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex flex-col gap-0.5 text-xs text-muted-foreground">
                        {f.phone && (
                          <span className="inline-flex items-center gap-1">
                            <Phone className="h-3 w-3" /> {f.phone}
                          </span>
                        )}
                        {f.email && f.email !== '[email protected]' && (
                          <span className="inline-flex items-center gap-1 truncate max-w-[16rem]">
                            <Mail className="h-3 w-3 shrink-0" /> {f.email}
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function FacilitiesPage() {
  return (
    <div className="max-w-7xl mx-auto px-4 md:px-6 py-8 space-y-8">
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary mt-0.5">
          <Activity className="h-5 w-5" />
        </span>
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-bold text-foreground">Facility Health Explorer</h2>
            <Badge variant="secondary" className="font-normal">
              Virtue Foundation · DAIS 2026
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Explore healthcare facilities — specialties, capacity, and reach — from the hackathon dataset.
          </p>
        </div>
      </div>

      <KpiRow />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle>Top medical specialties</CardTitle>
            <CardDescription>Most common services offered across facilities</CardDescription>
          </CardHeader>
          <CardContent>
            <SpecialtyBars />
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle>Facilities by bed capacity</CardTitle>
            <CardDescription>Distribution of reported bed capacity</CardDescription>
          </CardHeader>
          <CardContent>
            <DonutChart queryKey="facilities_by_capacity" xKey="band" yKey="facilities" height={300} />
          </CardContent>
        </Card>
      </div>

      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle>Facilities by city</CardTitle>
          <CardDescription>Where the most facilities are concentrated</CardDescription>
        </CardHeader>
        <CardContent>
          <BarChart
            queryKey="facilities_by_city"
            xKey="city"
            yKey="facilities"
            orientation="horizontal"
            height={340}
            showLegend={false}
          />
        </CardContent>
      </Card>

      <Directory />
    </div>
  );
}
