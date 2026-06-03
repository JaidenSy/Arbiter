import type { DriveStep } from 'driver.js'

export const TOUR_STEPS: DriveStep[] = [
  {
    element: '#nav-dashboard',
    popover: {
      title: 'Dashboard',
      description: 'Your command center. Live agent activity, request volume, latency, and error rates at a glance.',
      side: 'right',
      align: 'center',
    },
  },
  {
    element: '#nav-agents',
    popover: {
      title: 'Agents',
      description: 'Register and manage your AI agents. Each agent gets a scoped API key and a defined set of allowed tools.',
      side: 'right',
      align: 'center',
    },
  },
  {
    element: '#nav-mcp-servers',
    popover: {
      title: 'MCP Servers',
      description: 'Connect your Model Context Protocol servers. Arbiter routes tool calls here and enforces per-agent permissions.',
      side: 'right',
      align: 'center',
    },
  },
  {
    element: '#nav-vault',
    popover: {
      title: 'Vault',
      description: 'Encrypted secrets store. Agents can read secrets at runtime without them ever leaving the server.',
      side: 'right',
      align: 'center',
    },
  },
  {
    element: '#nav-sessions',
    popover: {
      title: 'Sessions',
      description: 'Full agent chain observability. Every request, tool call, and response, with latency and token traces.',
      side: 'right',
      align: 'center',
    },
  },
  {
    element: '#nav-permissions',
    popover: {
      title: 'Permissions',
      description: 'Tool-level access control. Grant or revoke specific MCP tools per agent with a single click.',
      side: 'right',
      align: 'center',
    },
  },
  {
    element: '#nav-organization',
    popover: {
      title: 'Organization',
      description: 'Invite teammates, manage roles, and view org-level usage.',
      side: 'right',
      align: 'center',
    },
  },
  {
    element: '#nav-settings',
    popover: {
      title: 'Settings',
      description: 'General preferences, billing, developer API keys, and app info all in one place.',
      side: 'right',
      align: 'center',
    },
  },
  {
    element: '#nav-docs',
    popover: {
      title: 'Docs',
      description: 'Setup guides, API reference, and integration examples — everything you need to connect your first agent.',
      side: 'right',
      align: 'center',
    },
  },
  {
    element: '#help-button',
    popover: {
      title: "That's it!",
      description: "Click this button any time to replay the tour. If you ever need help, reach out via <strong>Contact Support</strong> in your avatar menu.",
      side: 'right',
      align: 'center',
    },
  },
]
