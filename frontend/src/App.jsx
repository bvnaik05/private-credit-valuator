import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Navbar   from './components/Navbar'
import MarketBar from './components/MarketBar'
import Home      from './pages/Home'
import LoanScorer from './pages/LoanScorer'
import Portfolio  from './pages/Portfolio'

export default function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <MarketBar />
      <Routes>
        <Route path="/"          element={<Home />} />
        <Route path="/score"     element={<LoanScorer />} />
        <Route path="/portfolio" element={<Portfolio />} />
      </Routes>
    </BrowserRouter>
  )
}