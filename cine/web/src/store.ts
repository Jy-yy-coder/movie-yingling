import { create } from 'zustand'
import type { Planet } from './types'

interface GalaxyStore {
  planets: Planet[]
  planetsById: Record<string, Planet>
  loaded: boolean
  booted: boolean
  hoverId: string | null
  hoverPos: { x: number; y: number } | null
  selectedId: string | null
  interacting: boolean
  focusRegion: string
  focusGenre: string
  navigatorOpen: boolean
  setPlanets: (ps: Planet[]) => void
  setBooted: (b: boolean) => void
  setHover: (id: string | null) => void
  setHoverPos: (p: { x: number; y: number } | null) => void
  setSelected: (id: string | null) => void
  setInteracting: (b: boolean) => void
  setFocus: (region: string, genre: string) => void
  setNavigatorOpen: (b: boolean) => void
}

export const useGalaxy = create<GalaxyStore>((set) => ({
  planets: [],
  planetsById: {},
  loaded: false,
  booted: false,
  hoverId: null,
  hoverPos: null,
  selectedId: null,
  interacting: false,
  focusRegion: '',
  focusGenre: '',
  navigatorOpen: false,
  setPlanets: (ps) => set({ planets: ps, planetsById: Object.fromEntries(ps.map((p) => [p.id, p])), loaded: true }),
  setBooted: (b) => set({ booted: b }),
  setHover: (id) => set({ hoverId: id }),
  setHoverPos: (p) => set({ hoverPos: p }),
  setSelected: (id) => set({ selectedId: id }),
  setInteracting: (b) => set({ interacting: b }),
  setFocus: (region, genre) => set({ focusRegion: region, focusGenre: genre }),
  setNavigatorOpen: (b) => set({ navigatorOpen: b }),
}))
