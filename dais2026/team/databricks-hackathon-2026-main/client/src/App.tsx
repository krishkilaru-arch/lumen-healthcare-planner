import { createBrowserRouter, RouterProvider, NavLink, Outlet, Link } from 'react-router';
import { useState } from 'react';
import { Button, Sheet, SheetContent, SheetHeader, SheetTitle, useIsMobile } from '@databricks/appkit-ui/react';
import { Menu, Activity, Building2, Database, Sparkles, Bot, ArrowRight, MapPin } from 'lucide-react';
import { FacilitiesPage } from './pages/facilities/FacilitiesPage';
import { MapPage } from './pages/map/MapPage';
import { LakebasePage } from './pages/lakebase/LakebasePage';
import { GeniePage } from './pages/genie/GeniePage';
import { ServingPage } from './pages/serving/ServingPage';

const NAV = [
  { to: '/', label: 'Home', end: true },
  { to: '/facilities', label: 'Facilities', end: false },
  { to: '/map', label: 'Map', end: false },
  { to: '/genie', label: 'Genie', end: false },
  { to: '/assistant', label: 'Assistant', end: false },
  { to: '/worklist', label: 'Worklist', end: false },
];

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
    isActive ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground'
  }`;

const mobileNavLinkClass = ({ isActive }: { isActive: boolean }) =>
  `block px-3 py-2 rounded-md text-sm font-medium transition-colors ${
    isActive ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground'
  }`;

type NavLinkClassFn = (props: { isActive: boolean }) => string;

function NavLinks({
  className,
  linkClass,
  onClick,
}: {
  className?: string;
  linkClass: NavLinkClassFn;
  onClick?: () => void;
}) {
  return (
    <nav className={className}>
      {NAV.map((item) => (
        <NavLink key={item.to} to={item.to} end={item.end} className={linkClass} onClick={onClick}>
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}

function Layout() {
  const isMobile = useIsMobile();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur px-4 md:px-6 py-3 flex items-center gap-4">
        <Link to="/" className="flex items-center gap-2 shrink-0">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Activity className="h-5 w-5" />
          </span>
          <span className="text-lg font-semibold tracking-tight text-foreground">Lumen Virtue</span>
        </Link>
        <NavLinks className="hidden md:flex gap-1 ml-2" linkClass={navLinkClass} />
        <div className="ml-auto md:hidden">
          <Sheet open={isMobile && mobileNavOpen} onOpenChange={setMobileNavOpen}>
            <Button variant="ghost" size="icon" onClick={() => setMobileNavOpen(true)}>
              <Menu className="h-5 w-5" />
              <span className="sr-only">Open navigation</span>
            </Button>
            <SheetContent side="left">
              <SheetHeader>
                <SheetTitle>Navigation</SheetTitle>
              </SheetHeader>
              <NavLinks
                className="flex flex-col gap-1 mt-4"
                linkClass={mobileNavLinkClass}
                onClick={() => setMobileNavOpen(false)}
              />
            </SheetContent>
          </Sheet>
        </div>
      </header>

      <main className="flex-1 w-full">
        <Outlet />
      </main>

      <footer className="border-t px-4 md:px-6 py-4 text-xs text-muted-foreground">
        Lumen Virtue · Databricks AppKit · Healthcare facility intelligence on the Virtue Foundation dataset
      </footer>
    </div>
  );
}

const CAPABILITIES = [
  {
    to: '/facilities',
    title: 'Facility Health Explorer',
    icon: Building2,
    desc: 'Browse healthcare facilities by specialty, capacity, and city, and search the full directory.',
  },
  {
    to: '/map',
    title: 'Facility Map',
    icon: MapPin,
    desc: 'See every geocoded facility plotted on an interactive world map, clustered by location.',
  },
  {
    to: '/genie',
    title: 'Genie',
    icon: Sparkles,
    desc: 'Ask questions about the data in plain English and get governed SQL answers.',
  },
  {
    to: '/assistant',
    title: 'AI Assistant',
    icon: Bot,
    desc: 'Chat with Claude Opus 4.8 to draft outreach, summarize, and brainstorm.',
  },
  {
    to: '/worklist',
    title: 'Outreach Worklist',
    icon: Database,
    desc: 'A shared outreach checklist persisted in Lakebase Postgres — add, complete, delete.',
  },
];

function HomePage() {
  return (
    <div className="max-w-6xl mx-auto px-4 md:px-6 py-10 md:py-16 space-y-12">
      <section className="text-center max-w-2xl mx-auto space-y-4">
        <span className="inline-flex items-center gap-2 rounded-full bg-accent px-3 py-1 text-xs font-medium text-accent-foreground">
          <Activity className="h-3.5 w-3.5" /> Powered by Databricks AppKit
        </span>
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-foreground">
          Healthcare facility intelligence, in one place
        </h1>
        <p className="text-lg text-muted-foreground">
          A Lakebase-backed hackathon app exploring the Virtue Foundation facilities dataset, with natural-language
          Q&amp;A and a synced dataset for rapid demos and stakeholder reviews.
        </p>
        <div className="flex items-center justify-center gap-3 pt-2">
          <Button asChild size="lg">
            <Link to="/facilities">
              Explore facilities <ArrowRight className="ml-1 h-4 w-4" />
            </Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link to="/genie">Ask Genie</Link>
          </Button>
        </div>
      </section>

      <section className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        {CAPABILITIES.map(({ to, title, icon: Icon, desc }) => (
          <Link
            key={to}
            to={to}
            className="group rounded-xl border bg-card p-6 shadow-sm transition-all hover:shadow-md hover:border-primary/40"
          >
            <div className="flex items-start gap-4">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Icon className="h-5 w-5" />
              </span>
              <div className="space-y-1">
                <h3 className="font-semibold text-foreground flex items-center gap-1">
                  {title}
                  <ArrowRight className="h-4 w-4 opacity-0 -translate-x-1 transition-all group-hover:opacity-100 group-hover:translate-x-0" />
                </h3>
                <p className="text-sm text-muted-foreground">{desc}</p>
              </div>
            </div>
          </Link>
        ))}
      </section>
    </div>
  );
}

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/facilities', element: <FacilitiesPage /> },
      { path: '/map', element: <MapPage /> },
      { path: '/genie', element: <GeniePage /> },
      { path: '/assistant', element: <ServingPage /> },
      { path: '/worklist', element: <LakebasePage /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
