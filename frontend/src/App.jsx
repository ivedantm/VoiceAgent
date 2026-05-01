import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import LiveSession from './pages/LiveSession';
import History from './pages/History';
import Settings from './pages/Settings';
import './index.css';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/live" element={<LiveSession />} />
          <Route path="/history" element={<History />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
