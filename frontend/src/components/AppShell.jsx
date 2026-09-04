import { Link, Outlet } from 'react-router-dom'

export default function AppShell() {
  return (
    <div className="min-h-svh bg-zinc-100">
      <header className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3 sm:px-6">
          <Link to="/" className="block">
            <p className="text-sm font-semibold tracking-tight text-zinc-900">Stocklytic</p>
            <p className="text-xs text-zinc-500">Attention-first watchlist</p>
          </Link>
        </div>
      </header>
      <Outlet />
    </div>
  )
}
