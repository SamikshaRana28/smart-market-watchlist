import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import AppShell from './components/AppShell.jsx'
import StockDetail from './pages/StockDetail.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<App />} />
          <Route path="/symbol/:symbol" element={<StockDetail />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
