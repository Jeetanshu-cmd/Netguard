import { useContext } from 'react'
import { LiveDataContext } from '../context/liveDataContextDefinition.js'

export function useLiveData() {
  const ctx = useContext(LiveDataContext)
  if (!ctx) throw new Error('useLiveData must be used within a LiveDataProvider')
  return ctx
}
