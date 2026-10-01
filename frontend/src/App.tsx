import HealthCheck from './components/HealthCheck'
import './App.css'

function App() {
  return (
    <div className="app">
      <header>
        <h1>NewBody Content Auditor</h1>
        <p>Compare Instagram content across multiple accounts</p>
      </header>
      <main>
        <HealthCheck />
      </main>
    </div>
  )
}

export default App
