import { NavLink, Route, Routes } from 'react-router-dom';

import Capture from './pages/Capture';
import Results from './pages/Results';
import Validation from './pages/Validation';

export default function App() {
  return (
    <div className='app'>
      <header className='app-header'>
        <h1>Human Verification Queue</h1>
        <nav className='app-nav'>
          <NavLink to='/capture'>Upload</NavLink>
          <NavLink to='/result'>Results</NavLink>
          <NavLink to='/validation'>Validation</NavLink>
        </nav>
      </header>

      <main>
        <Routes>
          <Route path='/' element={<Capture />} />
          <Route path='/capture' element={<Capture />} />
          <Route path='/result' element={<Results />} />
          <Route path='/validation' element={<Validation />} />
          <Route path='*' element={<p>Page not found.</p>} />
        </Routes>
      </main>
    </div>
  );
}
