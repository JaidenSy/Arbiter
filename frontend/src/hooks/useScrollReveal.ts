import { useEffect, useRef } from 'react'

interface UseScrollRevealOptions {
  delay?: number
  threshold?: number
  rootMargin?: string
}

export function useScrollReveal<T extends HTMLElement = HTMLDivElement>({
  delay = 0,
  threshold = 0.12,
  rootMargin = '0px 0px -50px 0px',
}: UseScrollRevealOptions = {}) {
  const ref = useRef<T>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    // If already in viewport on load, skip animation entirely: no content gating
    const rect = el.getBoundingClientRect()
    const alreadyVisible = rect.top < window.innerHeight && rect.bottom > 0
    if (alreadyVisible) return

    // Add will-animate only after mount so initial server/headless render stays visible
    el.classList.add('reveal-target', 'will-animate')
    if (delay > 0) el.style.transitionDelay = `${delay}ms`

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          el.classList.add('revealed')
          // Clean up delay after reveal so it doesn't affect future transitions
          if (delay > 0) {
            el.addEventListener('transitionend', () => {
              el.style.transitionDelay = ''
            }, { once: true })
          }
          observer.disconnect()
        }
      },
      { threshold, rootMargin }
    )

    observer.observe(el)
    return () => observer.disconnect()
  }, [delay, threshold, rootMargin])

  return ref
}
