import React, { useEffect } from 'react';
import {
  LayoutDashboard, UtensilsCrossed, TrendingUp, Target,
  MessageSquare, Sparkles, ChefHat, Dumbbell, Wallet,
  Globe, CalendarDays, Trophy, Menu, X, LogOut,
} from 'lucide-react';

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
      {/* Backdrop for the mobile drawer */}
      {sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          style={{
            position: 'fixed', inset: 0, zIndex: 35,
            background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(2px)',
          }}
        />
      )}

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
          <div className="flex items-center" style={{ gap: '0.625rem', padding: '0 0.75rem 0.625rem' }}>
            <div
              className="flex items-center justify-center"
              style={{
                width: 32, height: 32, borderRadius: 999,
                background: '#2A3240', fontSize: '0.75rem', fontWeight: 700, color: '#EEF2F7',
              }}
            >
              {initials}
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: '0.8125rem', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {user?.full_name || user?.username || 'Athlete'}
              </div>
              <div style={{ fontSize: '0.6875rem', color: '#667085' }}>View profile</div>
            </div>
          </div>
          <button className="nav-item" onClick={onLogout}>
            <LogOut size={17} />
            <span>Sign out</span>
          </button>
        </div>
      </aside>

      <main className="shell-main">
        {/* Mobile top bar */}
        <div
          className="flex items-center justify-between mobile-topbar"
          style={{ marginBottom: '1.25rem' }}
        >
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label="Open navigation"
            style={{ background: 'none', border: 'none', color: '#EEF2F7', cursor: 'pointer', padding: 4 }}
          >
            <Menu size={22} />
          </button>
          <span style={{ fontWeight: 600, fontSize: '0.9375rem' }}>{current?.label || 'NutriPlan'}</span>
          <div style={{ width: 22 }} />
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
    </div>
  );
}
