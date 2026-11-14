/**
 * Main navigation (§2.3). Pages that are not built yet render `PlaceholderPage` with the roadmap
 * phase that delivers them (§15). Labels: `nav.<section>.title` / `nav.<section>.<page>`.
 */

export interface NavPage {
  key: string
  path: string
  phase: number
}

export interface NavSection {
  key: string
  icon: string
  pages: NavPage[]
}

function section(key: string, icon: string, phase: number, pages: string[]): NavSection {
  const base = `/${key.replace(/_/g, '-')}`
  return {
    key,
    icon,
    pages: pages.map((page) => ({ key: page, path: `${base}/${page.replace(/_/g, '-')}`, phase })),
  }
}

export const NAVIGATION: NavSection[] = [
  { key: 'overview', icon: 'bi-speedometer2', pages: [{ key: 'dashboard', path: '/', phase: 0 }] },
  section('app_store', 'bi-grid-3x3-gap', 3, ['browse', 'installed', 'updates']),
  section('projects', 'bi-rocket-takeoff', 4, ['list', 'git_credentials']),
  section('websites', 'bi-globe2', 2, ['sites', 'runtimes']),
  section('domains', 'bi-shield-lock', 2, [
    'domains',
    'dns_accounts',
    'dns_zones',
    'certificates',
    'acme_accounts',
  ]),
  section('databases', 'bi-database', 3, ['servers', 'databases', 'users']),
  section('containers', 'bi-box-seam', 1, [
    'containers',
    'compose',
    'images',
    'networks',
    'volumes',
    'registries',
    'settings',
  ]),
  section('files', 'bi-folder2-open', 1, ['manager', 'recycle_bin']),
  section('terminal', 'bi-terminal', 1, ['local', 'ssh_hosts', 'container_exec', 'snippets']),
  section('host', 'bi-hdd-rack', 1, [
    'monitoring',
    'processes',
    'services',
    'firewall',
    'ssh',
    'fail2ban',
    'disks',
    'network',
  ]),
  section('cronjobs', 'bi-clock-history', 5, ['jobs', 'history']),
  section('backups', 'bi-cloud-arrow-up', 5, ['records', 'accounts', 'snapshots']),
  section('logs', 'bi-journal-text', 1, ['audit', 'login', 'tasks', 'system', 'websites']),
  section('toolbox', 'bi-tools', 5, [
    'cleanup',
    'swap',
    'time',
    'hostname',
    'antivirus',
    'daemons',
    'scripts',
  ]),
  section('settings', 'bi-gear', 5, [
    'general',
    'security',
    'notifications',
    'network',
    'updates',
    'about',
  ]),
]

// Phases where a section's pages differ from the section default.
const PHASE_OVERRIDES: Record<string, number> = {
  '/host/firewall': 5,
  '/host/ssh': 5,
  '/host/fail2ban': 5,
  '/host/disks': 5,
  '/host/network': 5,
  '/logs/websites': 2,
}

for (const s of NAVIGATION) {
  for (const p of s.pages) p.phase = PHASE_OVERRIDES[p.path] ?? p.phase
}
