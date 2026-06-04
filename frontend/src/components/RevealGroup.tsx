import React, { useEffect, useRef } from 'react'

interface RevealGroupProps {
  children: React.ReactNode
  stagger?: number
  className?: string
  threshold?: number
  rootMargin?: string
}

/**
 * Wraps direct children in a reveal container.
 * Each child fades + slides in on scroll with staggered delays.
 * Content is visible by default — animation only applies to off-screen elements.
 */
export function RevealGroup({
  children,
  stagger = 80,
  className,
  threshold = 0.12,
  rootMargin = '0px 0px -50px 0px',
}: RevealGroupProps): React.ReactElement {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const items = Array.from(container.children) as HTMLElement[]

    // Check if the group is already visible on load
    const rect = container.getBoundingClientRect()
    const alreadyVisible = rect.top < window.innerHeight && rect.bottom > 0
    if (alreadyVisible) return

    // Stamp will-animate + stagger delay on each child after mount
    items.forEach((item, i) => {
      item.classList.add('reveal-target', 'will-animate')
      item.style.transitionDelay = `${i * stagger}ms`
    })

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          items.forEach(item => item.classList.add('revealed'))
          observer.disconnect()
        }
      },
      { threshold, rootMargin }
    )

    observer.observe(container)
    return () => observer.disconnect()
  }, [stagger, threshold, rootMargin])

  return (
    <div ref={containerRef} className={className}>
      {children}
    </div>
  )
}
