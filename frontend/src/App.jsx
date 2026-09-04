// import { useCallback, useEffect, useMemo, useState } from 'react'
// import { loadDashboardData } from './api.js'
// import ChangeCard from './components/ChangeCard.jsx'
// import Hero from './components/Hero.jsx'
// import WatchlistTable from './components/WatchlistTable.jsx'
// import { isMeaningful, sectorCorrelationBanners } from './format.js'

// export default function App() {
//   const [data, setData] = useState(null)
//   const [error, setError] = useState(null)
//   const [loading, setLoading] = useState(true)

//   const refresh = useCallback(async () => {
//     setLoading(true)
//     setError(null)
//     try {
//       const payload = await loadDashboardData()
//       setData(payload)
//     } catch (err) {
//       setError(err instanceof Error ? err.message : 'Failed to load watchlist')
//     } finally {
//       setLoading(false)
//     }
//   }, [])

//   useEffect(() => {
//     refresh()
//   }, [refresh])

//   const changes = data?.changes ?? []
//   const meaningful = useMemo(() => changes.filter(isMeaningful), [changes])
//   const sectorBanners = useMemo(() => sectorCorrelationBanners(changes), [changes])

//   return (
//     <main className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">
//       <div className="flex justify-end">
//         <button
//           type="button"
//           onClick={refresh}
//           className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-100"
//         >
//           Refresh
//         </button>
//       </div>

//       <Hero
//         loading={loading && !data}
//         changeCount={meaningful.length}
//         lastViewedAt={data?.last_viewed_at}
//         watchlistName={data?.watchlist?.name}
//         stale={data?.stale}
//         marketStatus={data?.market_status}
//         lastUpdated={data?.last_updated}
//       />

//       {error && (
//         <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
//           Could not load market changes. {error}
//         </div>
//       )}

//       {sectorBanners.map((message) => (
//         <div
//           key={message}
//           className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-950"
//           role="status"
//         >
//           {message}
//         </div>
//       ))}

//       <section>
//         <div className="mb-3 flex items-baseline justify-between">
//           <h2 className="text-sm font-semibold text-zinc-900">Worth your attention</h2>
//           <p className="text-xs text-zinc-500">Sorted by Attention Score</p>
//         </div>
//         {loading && !data ? (
//           <div className="grid gap-3 sm:grid-cols-2">
//             {[0, 1, 2].map((key) => (
//               <div
//                 key={key}
//                 className="h-32 animate-pulse rounded-xl border border-zinc-200 bg-white"
//               />
//             ))}
//           </div>
//         ) : meaningful.length === 0 ? (
//           <p className="rounded-xl border border-dashed border-zinc-200 bg-white px-4 py-6 text-sm text-zinc-500">
//             Nothing unusual versus your last visit. Full list is below.
//           </p>
//         ) : (
//           <div className="grid gap-3 sm:grid-cols-2">
//             {meaningful.map((row) => (
//               <ChangeCard key={row.symbol} row={row} />
//             ))}
//           </div>
//         )}
//       </section>

//       {loading && !data ? (
//         <div className="h-48 animate-pulse rounded-2xl border border-zinc-200 bg-white" />
//       ) : (
//         <WatchlistTable rows={changes} />
//       )}
//     </main>
//   )
// }



import { useCallback, useEffect, useMemo, useState } from 'react'
import { loadDashboardData } from './api.js'
import ChangeCard from './components/ChangeCard.jsx'
import Hero from './components/Hero.jsx'
import WatchlistTable from './components/WatchlistTable.jsx'
import { isMeaningful, sectorCorrelationBanners } from './format.js'

const SENSITIVITY_OPTIONS = [
  { value: 'conservative', label: 'Conservative' },
  { value: 'balanced', label: 'Balanced' },
  { value: 'aggressive', label: 'Aggressive' },
]

export default function App() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [sensitivity, setSensitivity] = useState('balanced')

  const refresh = useCallback(async (nextSensitivity) => {
    setLoading(true)
    setError(null)
    try {
      const payload = await loadDashboardData(nextSensitivity ?? sensitivity)
      setData(payload)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load watchlist')
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    refresh(sensitivity)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sensitivity])

  const handleSensitivityChange = (event) => {
    setSensitivity(event.target.value)
  }

  const changes = data?.changes ?? []
  const meaningful = useMemo(() => changes.filter(isMeaningful), [changes])
  const sectorBanners = useMemo(() => sectorCorrelationBanners(changes), [changes])

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <label className="flex items-center gap-2 text-xs font-medium text-zinc-600">
          Sensitivity
          <select
            value={sensitivity}
            onChange={handleSensitivityChange}
            className="rounded-lg border border-zinc-200 bg-white px-2 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 focus:outline-none focus:ring-2 focus:ring-zinc-300"
          >
            {SENSITIVITY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={() => refresh()}
          className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-100"
        >
          Refresh
        </button>
      </div>

      <Hero
        loading={loading && !data}
        changeCount={meaningful.length}
        lastViewedAt={data?.last_viewed_at}
        watchlistName={data?.watchlist?.name}
        stale={data?.stale}
        marketStatus={data?.market_status}
        lastUpdated={data?.last_updated}
      />

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          Could not load market changes. {error}
        </div>
      )}

      {sectorBanners.map((message) => (
        <div
          key={message}
          className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-950"
          role="status"
        >
          {message}
        </div>
      ))}

      <section>
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="text-sm font-semibold text-zinc-900">Worth your attention</h2>
          <p className="text-xs text-zinc-500">Sorted by Attention Score</p>
        </div>
        {loading && !data ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {[0, 1, 2].map((key) => (
              <div
                key={key}
                className="h-32 animate-pulse rounded-xl border border-zinc-200 bg-white"
              />
            ))}
          </div>
        ) : meaningful.length === 0 ? (
          <p className="rounded-xl border border-dashed border-zinc-200 bg-white px-4 py-6 text-sm text-zinc-500">
            Nothing unusual versus your last visit. Full list is below.
          </p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {meaningful.map((row) => (
              <ChangeCard key={row.symbol} row={row} />
            ))}
          </div>
        )}
      </section>

      {loading && !data ? (
        <div className="h-48 animate-pulse rounded-2xl border border-zinc-200 bg-white" />
      ) : (
        <WatchlistTable rows={changes} />
      )}
    </main>
  )
}
