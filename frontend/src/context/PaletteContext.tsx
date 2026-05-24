import React, { createContext, useCallback, useContext, useState } from 'react'

interface PaletteContextValue {
  isOpen: boolean
  open:   () => void
  close:  () => void
}

const PaletteContext = createContext<PaletteContextValue>({
  isOpen: false,
  open:   () => {},
  close:  () => {},
})

export function PaletteProvider({ children }: { children: React.ReactNode }): React.ReactElement {
  const [isOpen, setIsOpen] = useState(false)
  const open  = useCallback(() => setIsOpen(true),  [])
  const close = useCallback(() => setIsOpen(false), [])

  return (
    <PaletteContext.Provider value={{ isOpen, open, close }}>
      {children}
    </PaletteContext.Provider>
  )
}

export function usePalette(): PaletteContextValue {
  return useContext(PaletteContext)
}
