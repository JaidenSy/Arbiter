import React from 'react'
import { Helmet } from 'react-helmet-async'
import { useLocation } from 'react-router-dom'
import {
  SITE_URL,
  DEFAULT_META,
  PAGE_META,
  NOINDEX_PATHS,
  NOINDEX_PREFIXES,
} from '../seo/routeMeta'

/**
 * Injects per-route SEO <head> tags for the SPA: a unique title/description,
 * canonical URL, Open Graph + Twitter fields, and robots noindex for non-public
 * routes. Mounted once near the root of <App>; reads the active route via
 * useLocation, so it must render inside the Router.
 */
export default function RouteMeta(): React.ReactElement {
  const { pathname } = useLocation()

  // Normalize: drop a trailing slash except for the root path.
  const path =
    pathname.length > 1 && pathname.endsWith('/')
      ? pathname.slice(0, -1)
      : pathname

  const isNoindex =
    NOINDEX_PATHS.has(path) ||
    NOINDEX_PREFIXES.some((prefix) => path.startsWith(prefix))

  const meta = PAGE_META[path] ?? DEFAULT_META

  // /login and /register render the marketing Landing: canonicalize to home.
  const canonicalPath = path === '/login' || path === '/register' ? '/' : path
  const canonical = `${SITE_URL}${canonicalPath}`

  return (
    <Helmet>
      <title>{meta.title}</title>
      <meta name="description" content={meta.description} />
      <link rel="canonical" href={canonical} />

      <meta property="og:title" content={meta.title} />
      <meta property="og:description" content={meta.description} />
      <meta property="og:url" content={canonical} />

      <meta name="twitter:title" content={meta.title} />
      <meta name="twitter:description" content={meta.description} />

      {isNoindex && <meta name="robots" content="noindex, follow" />}
    </Helmet>
  )
}
