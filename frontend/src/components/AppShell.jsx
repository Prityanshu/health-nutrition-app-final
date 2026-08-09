import React, { useEffect, useState } from 'react';
import {
  LayoutDashboard, UtensilsCrossed, TrendingUp, Target,
  MessageSquare, Sparkles, ChefHat, Dumbbell, Wallet,
  Globe, CalendarDays, Trophy, Menu, X, LogOut,
} from 'lucide-react';
import ToastHost from '../Toast';

/**
 * Persistent application shell.
 *
 * Replaces the previous hub-and-spoke navigation, where every feature was
 * reached from the dashboard and required a "Back to Dashboard" button to
 * leave. A fixed rail on desktop and a tab bar on mobile means any view is
 * one click from any other.
 */

export const NAV_GROUPS = [
  {
    label: 'Today',
    items: [
      { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
      { id: 'log-meal', label: 'Log Meal', icon: UtensilsCrossed },
      { id: 'view-progress', label: 'Progress', icon: TrendingUp },
      { id: 'set-goals', label: 'Goals', icon: Target },
    ],
  },
  {
    label: 'AI Coach',
    items: [
      { id: 'chatbot', label: 'Assistant', icon: MessageSquare },
      { id: 'ml-recommendations', label: 'For You', icon: Sparkles },
      // 'ai-recipes' removed from navigation - the view had no working content
      // and its ChefGenius half now lives on its own page under Specialists.
      // renderAIRecipes remains in App.js but is unreachable.
    ],
  },
  {
    label: 'Specialists',
    items: [
      { id: 'chefgenius', label: 'ChefGenius', icon: ChefHat },
      { id: 'fitmentor', label: 'FitMentor', icon: Dumbbell },
      { id: 'budgetchef', label: 'BudgetChef', icon: Wallet },
      { id: 'culinaryexplorer', label: 'Explorer', icon: Globe },
      { id: 'advancedmealplanner', label: 'Meal Planner', icon: CalendarDays },
    ],
  },
  {
    label: 'Motivation',
    items: [{ id: 'enhanced-challenges', label: 'Challenges', icon: Trophy }],
  },
];

// The five most-used destinations get the mobile tab bar.
const MOBILE_TABS = ['dashboard', 'log-meal', 'chatbot', 'view-progress', 'enhanced-challenges'];

export default function AppShell({
  activeView,
  onNavigate,
  user,
  points,
  onLogout,
  sidebarOpen,
  setSidebarOpen,
  children,
}) {
  // Scope the dark theme to the shell so views rendered outside it (login,
  // register) keep the original light styling.
  useEffect(() => {
    document.body.classList.add('theme-dark');
    return () => document.body.classList.remove('theme-dark');
  }, []);

  // A hairline under the sticky top bar, but only once the page has actually
  // scrolled. Always-on reads as a boxed-in header; never-on makes content
  // appear to slide under nothing.
  const [stuck, setStuck] = useState(false);
  useEffect(() => {
    const onScroll = () => setStuck(window.scrollY > 4);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // Lock the page behind the drawer. Without this the dashboard scrolls under
  // the open menu, which feels like two screens fighting each other.
  useEffect(() => {
    document.body.classList.toggle('drawer-open', Boolean(sidebarOpen));
    return () => document.body.classList.remove('drawer-open');
  }, [sidebarOpen]);

  // Close the mobile drawer whenever the destination changes.
  useEffect(() => {
    setSidebarOpen(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeView]);

  const allItems = NAV_GROUPS.flatMap((g) => g.items);
  const mobileItems = MOBILE_TABS
    .map((id) => allItems.find((i) => i.id === id))
    .filter(Boolean);
  const current = allItems.find((i) => i.id === activeView);

  const initials = (user?.full_name || user?.username || 'U')
    .split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase();

  return (
    <div className="app-shell">
      {/* Backdrop for the mobile drawer.
          z-index 55 puts it above the bottom nav (45): at 35 the tab bar
          stayed bright over the dimmed page, so the drawer looked half-open.
          Kept mounted and faded rather than unmounted, so closing animates
          out instead of vanishing. */}
      <div
        onClick={() => setSidebarOpen(false)}
        aria-hidden={!sidebarOpen}
        className={`nav-scrim ${sidebarOpen ? 'is-open' : ''}`}
      />

      <aside className={`nav-rail ${sidebarOpen ? 'nav-rail-open' : ''}`}>
        <div className="flex items-center justify-between" style={{ padding: '0 0.75rem 1.25rem' }}>
          <div className="flex items-center" style={{ gap: '0.625rem' }}>
            <div
              className="flex items-center justify-center"
              style={{
                width: 34, height: 34, borderRadius: 10,
                background: 'linear-gradient(135deg,#8B5CF6,#22D3EE)',
                boxShadow: '0 0 20px -4px rgba(139,92,246,0.6)',
              }}
            >
              <Sparkles size={18} color="#fff" />
            </div>
            <span style={{ fontWeight: 700, fontSize: '0.95rem', letterSpacing: '-0.01em' }}>
              NutriPlan
            </span>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            aria-label="Close navigation"
            className="nav-close"
            style={{ background: 'none', border: 'none', color: '#98A2B3', cursor: 'pointer' }}
          >
            <X size={18} />
          </button>
        </div>

        <nav style={{ flex: 1 }}>
          {NAV_GROUPS.map((group) => (
            <div key={group.label}>
              <div className="nav-section">{group.label}</div>
              {group.items.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => onNavigate(id)}
                  className={`nav-item ${activeView === id ? 'nav-item-active' : ''}`}
                  aria-current={activeView === id ? 'page' : undefined}
                >
                  <Icon size={17} />
                  <span>{label}</span>
                </button>
              ))}
            </div>
          ))}
        </nav>

        <div style={{ borderTop: '1px solid #2A3240', paddingTop: '0.75rem', marginTop: '0.75rem' }}>
          {/* This said "View profile" and went nowhere for the whole life of
              the app. It is a button now. */}
          <button
            className={`nav-item ${activeView === 'profile' ? 'is-active' : ''}`}
            onClick={() => onNavigate('profile')}
            style={{ gap: '0.625rem', width: '100%' }}
          >
            <div
              className="flex items-center justify-center"
              style={{
                width: 32, height: 32, borderRadius: 999, flexShrink: 0,
                background: activeView === 'profile'
                  ? 'linear-gradient(135deg,#8B5CF6,#22D3EE)' : '#2A3240',
                fontSize: '0.75rem', fontWeight: 700,
                color: activeView === 'profile' ? '#0B0E14' : '#EEF2F7',
              }}
            >
              {initials}
            </div>
            <div style={{ minWidth: 0, textAlign: 'left' }}>
              <div style={{ fontSize: '0.8125rem', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {user?.full_name || user?.username || 'Athlete'}
              </div>
              <div style={{ fontSize: '0.6875rem', color: '#667085' }}>
                {points != null ? `${points.toLocaleString()} points` : 'View profile'}
              </div>
            </div>
          </button>
          <button className="nav-item" onClick={onLogout}>
            <LogOut size={17} />
            <span>Sign out</span>
          </button>
        </div>
      </aside>

      <main className="shell-main">
        {/* Mobile top bar */}
        {/* The menu button was a bare 22px icon flush against the status bar:
            a small target in the hardest corner of the screen to reach. It is
            now a 44px tapable surface - the smallest size that is comfortable
            with a thumb - with the title beside it rather than centred, so the
            row reads left to right like the rest of the app. */}
        <div className={`mobile-topbar ${stuck ? "is-stuck" : ""}`}>
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label="Open navigation"
            className="topbar-menu"
          >
            <Menu size={20} />
          </button>
          <span className="topbar-title">{current?.label || 'NutriPlan'}</span>
        </div>

        {children}
      </main>

      <nav className="bottom-nav" aria-label="Primary">
        {mobileItems.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => onNavigate(id)}
            className={`bottom-nav-item ${activeView === id ? 'bottom-nav-item-active' : ''}`}
            aria-current={activeView === id ? 'page' : undefined}
          >
            <Icon size={19} />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      {/* Mounted once, for the whole app. Any module can call toast() without
          threading a callback down through every screen. */}
      <ToastHost />
    </div>
  );
}
