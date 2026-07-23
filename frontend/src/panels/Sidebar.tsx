import React from "react";
import {
  Activity,
  ClipboardList,
  Columns3,
  GitPullRequest,
  LayoutGrid,
  Network,
  PanelLeftClose,
  PanelLeftOpen,
  Rocket,
  Settings,
  ShieldCheck,
} from "lucide-react";

export type NavKey =
  | "overview"
  | "jobs"
  | "provisioning"
  | "pipelines"
  | "moduleGraph"
  | "boards"
  | "audit"
  | "approvals"
  | "settings";

export type NavItem = { key: NavKey; label: string; icon: React.ComponentType<{ size?: number }>; badge?: number };

export function buildNavItems(pendingApprovals: number): NavItem[] {
  return [
    { key: "overview", label: "Overview", icon: LayoutGrid },
    { key: "jobs", label: "Jobs", icon: Activity },
    { key: "provisioning", label: "Provisioning", icon: Rocket },
    { key: "pipelines", label: "PRs & Pipelines", icon: GitPullRequest },
    { key: "moduleGraph", label: "Module Graph", icon: Network },
    { key: "boards", label: "Boards", icon: Columns3 },
    { key: "audit", label: "Audit", icon: ClipboardList },
    { key: "approvals", label: "Approvals", icon: ShieldCheck, badge: pendingApprovals || undefined },
    { key: "settings", label: "Settings", icon: Settings },
  ];
}

export function Sidebar({
  active,
  onSelect,
  collapsed,
  onToggleCollapsed,
  pendingApprovals,
}: {
  active: NavKey;
  onSelect: (key: NavKey) => void;
  collapsed: boolean;
  onToggleCollapsed: () => void;
  pendingApprovals: number;
}) {
  const items = buildNavItems(pendingApprovals);

  return (
    <aside className={`sidebar ${collapsed ? "collapsed" : ""}`} aria-label="Primary navigation">
      <div className="sidebarBrand">
        <span className="sidebarMark" aria-hidden="true">P</span>
        {collapsed ? null : <span className="sidebarWordmark">Platt</span>}
      </div>
      <nav className="sidebarNav">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.key}
              type="button"
              className={`sidebarNavItem ${active === item.key ? "active" : ""}`}
              onClick={() => onSelect(item.key)}
              aria-current={active === item.key ? "page" : undefined}
              title={collapsed ? item.label : undefined}
            >
              <Icon size={18} />
              {collapsed ? null : <span>{item.label}</span>}
              {item.badge ? <span className="sidebarNavBadge">{item.badge}</span> : null}
            </button>
          );
        })}
      </nav>
      <button type="button" className="sidebarCollapseToggle" onClick={onToggleCollapsed} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
        {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
        {collapsed ? null : <span>Collapse</span>}
      </button>
    </aside>
  );
}
