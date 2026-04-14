/**
 * ME2 Zustand stores — global state management.
 */

import { create } from 'zustand'

// ---------------------------------------------------------------------------
// Auth store
// ---------------------------------------------------------------------------

export const useAuthStore = create((set) => ({
  token: localStorage.getItem('me2_token') || null,
  user: null,

  setAuth: (token, user) => {
    localStorage.setItem('me2_token', token)
    set({ token, user })
  },

  logout: () => {
    localStorage.removeItem('me2_token')
    set({ token: null, user: null })
  },
}))

// ---------------------------------------------------------------------------
// Equipment store — live data from WebSocket
// ---------------------------------------------------------------------------

export const useEquipmentStore = create((set) => ({
  equipment: [],
  liveData: {},  // keyed by equipment id

  setEquipment: (equipment) => set({ equipment }),

  updateLiveData: (equipmentId, data) =>
    set((state) => ({
      liveData: { ...state.liveData, [equipmentId]: data },
    })),
}))

// ---------------------------------------------------------------------------
// Alerts store
// ---------------------------------------------------------------------------

export const useAlertStore = create((set) => ({
  activeAlerts: [],

  setAlerts: (alerts) => set({ activeAlerts: alerts }),

  addAlert: (alert) =>
    set((state) => ({
      activeAlerts: [...state.activeAlerts, alert],
    })),

  removeAlert: (alertId) =>
    set((state) => ({
      activeAlerts: state.activeAlerts.filter((a) => a.id !== alertId),
    })),
}))

// ---------------------------------------------------------------------------
// UI store
// ---------------------------------------------------------------------------

export const useUIStore = create((set) => ({
  selectedShift: null,  // null = current shift auto
  selectedDate: null,    // null = today
  sidebarOpen: true,

  setShift: (shift) => set({ selectedShift: shift }),
  setDate: (date) => set({ selectedDate: date }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
}))
