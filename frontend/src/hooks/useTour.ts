import { useCallback, useEffect, useRef } from 'react'
import { driver } from 'driver.js'
import 'driver.js/dist/driver.css'
import { TOUR_STEPS } from '../tour/tourSteps'

const TOUR_SEEN_KEY = 'arbiter_tour_seen_v1'

export function useTour(): { startTour: () => void } {
  const driverRef = useRef<ReturnType<typeof driver> | null>(null)

  const startTour = useCallback(() => {
    if (!driverRef.current) {
      driverRef.current = driver({
        showProgress: true,
        progressText: '{{current}} of {{total}}',
        animate: true,
        overlayOpacity: 0.55,
        popoverClass: 'arbiter-tour-popover',
        steps: TOUR_STEPS,
        onDestroyStarted: () => {
          localStorage.setItem(TOUR_SEEN_KEY, '1')
          driverRef.current?.destroy()
        },
      })
    }
    driverRef.current.drive()
  }, [])

  useEffect(() => {
    const seen = localStorage.getItem(TOUR_SEEN_KEY)
    if (!seen) {
      const timer = setTimeout(startTour, 800)
      return () => clearTimeout(timer)
    }
  }, [startTour])

  return { startTour }
}
