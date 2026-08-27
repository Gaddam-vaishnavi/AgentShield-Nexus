import { useState } from 'react'
import './App.css'

const ATTACK_API_URL = 'http://127.0.0.1:8000/risk/demo/attack'

const normalScenario = {
  label: 'NORMAL COMMERCE',
  score: 49,
  level: 'MEDIUM',
  action: 'MONITOR',
  velocity: 80,
  synchronization: 44,
  inventory: 21,
  behavior: 100,
  agents: 5000,
  requested: 2285,
  remaining: 715,
  protected: 0,
  description:
    'Moderate activity detected. Continue normal commerce while monitoring behavior.',
}

const initialAttackScenario = {
  label: 'INVENTORY CORNERING ATTACK',
  score: 100,
  level: 'CRITICAL',
  action: 'PROTECT_INVENTORY',
  velocity: 100,
  synchronization: 100,
  inventory: 100,
  behavior: 100,
  agents: 500,
  requested: 3477,
  remaining: 1400,
  protected: 600,
  description:
    'Critical collective inventory risk detected. AgentShield recommends protecting scarce inventory.',
}

function App() {
  const [scenario, setScenario] = useState('attack')
  const [attackData, setAttackData] = useState(initialAttackScenario)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [attackError, setAttackError] = useState(null)

  const data = scenario === 'normal' ? normalScenario : attackData

  const runScenario = (name) => {
    setScenario(name)

    if (name === 'attack') {
      fetchAttackScenario()
    }
  }

  const fetchAttackScenario = async () => {
    setIsAnalyzing(true)
    setAttackError(null)

    try {
      const response = await fetch(ATTACK_API_URL, {
        method: 'POST',
      })

      if (!response.ok) {
        throw new Error(`AgentShield API returned status ${response.status}`)
      }

      const result = await response.json()

      setAttackData((previous) => ({
        ...previous,
        score: result.risk_score,
        level: result.risk_level,
        action: result.action,
        description: result.reason,
        velocity: result.signals.velocity,
        synchronization: result.signals.synchronization,
        inventory: result.signals.inventory_impact,
        behavior: result.signals.behavior_coordination,
      }))
    } catch (err) {
      setAttackError(
        'Could not reach the AgentShield risk engine. Make sure the backend is running at ' +
          ATTACK_API_URL
      )
    } finally {
      setIsAnalyzing(false)
    }
  }

  return (
    <div className="app">
      <header className="header">
        <div>
          <div className="brand">
            <span className="shield">◆</span>
            <span>AgentShield</span>
          </div>
          <p>Agentic Commerce Risk Protection</p>
        </div>

        <div className="system-status">
          <span className="status-dot"></span>
          Protection Engine Online
        </div>
      </header>

      <main>
        <section className="hero-grid">
          <div className="risk-card">
            <div className="card-label">COLLECTIVE RISK</div>

            {scenario === 'attack' && isAnalyzing ? (
              <>
                <div className="risk-score">
                  Analyzing...
                </div>
                <p>Contacting the AgentShield risk engine and running the attack simulation.</p>
              </>
            ) : (
              <>
                <div className="risk-score">
                  {data.score}
                  <span>/100</span>
                </div>

                <div className={`risk-level ${data.level.toLowerCase()}`}>
                  {data.level}
                </div>

                <p>{data.description}</p>
              </>
            )}

            <div className="scenario-label">{data.label}</div>

            {scenario === 'attack' && attackError && (
              <p style={{ color: '#ff5c5c', marginTop: '0.75rem' }}>
                {attackError}
              </p>
            )}
          </div>

          <div className="decision-card">
            <div className="card-label">PROTECTION DECISION</div>

            <div className="decision-icon">!</div>

            <h2>{isAnalyzing && scenario === 'attack' ? 'ANALYZING...' : data.action}</h2>

            <p>
              {data.level === 'CRITICAL'
                ? 'Critical collective inventory risk detected.'
                : 'Moderate collective risk detected.'}
            </p>

            <div className="decision-explanation">
              {data.action === 'PROTECT_INVENTORY'
                ? 'Protect scarce inventory from coordinated automated purchasing.'
                : 'Continue the transaction while monitoring agent behavior.'}
            </div>
          </div>
        </section>

        <section className="signals-section">
          <div className="section-title">
            <div>
              <h2>Risk Signals</h2>
              <p>Four independent signals contribute to the collective risk score.</p>
            </div>
          </div>

          <div className="signals-grid">
            <SignalCard
              title="Purchase Velocity"
              value={data.velocity}
              description="Purchase attempts per second"
            />

            <SignalCard
              title="Synchronization"
              value={data.synchronization}
              description="Unique agents acting together"
            />

            <SignalCard
              title="Inventory Impact"
              value={data.inventory}
              description="Pressure placed on available stock"
            />

            <SignalCard
              title="Behavior Coordination"
              value={data.behavior}
              description="Similarity and timing alignment"
            />
          </div>
        </section>

        <section className="inventory-card">
          <div className="section-title">
            <div>
              <h2>Inventory Protection</h2>
              <p>Simulation of the effect of AgentShield protection.</p>
            </div>
          </div>

          <div className="inventory-grid">
            <Metric
              label="Starting Inventory"
              value="3,000"
            />

            <Metric
              label="Requested Quantity"
              value={data.requested.toLocaleString()}
            />

            <Metric
              label="Available After Protection"
              value={data.remaining.toLocaleString()}
            />

            <Metric
              label="Protected Reserve"
              value={data.protected.toLocaleString()}
            />
          </div>

          <div className="inventory-bar">
            <div
              className="inventory-used"
              style={{
                width: `${Math.max(
                  5,
                  100 - (data.remaining / 3000) * 100
                )}%`,
              }}
            ></div>
          </div>

          <div className="inventory-legend">
            <span>Inventory utilization</span>
            <span>{Math.round(((3000 - data.remaining) / 3000) * 100)}%</span>
          </div>
        </section>

        <section className="scenario-section">
          <div className="section-title">
            <div>
              <h2>Attack Simulation</h2>
              <p>Compare normal commerce with a coordinated inventory attack.</p>
            </div>
          </div>

          <div className="scenario-buttons">
            <button
              className={scenario === 'normal' ? 'active' : ''}
              onClick={() => runScenario('normal')}
              disabled={isAnalyzing}
            >
              Run Normal Scenario
            </button>

            <button
              className={scenario === 'attack' ? 'active attack-button' : ''}
              onClick={() => runScenario('attack')}
              disabled={isAnalyzing}
            >
              {isAnalyzing ? 'Analyzing...' : 'Run Attack Scenario'}
            </button>
          </div>
        </section>

        <section className="comparison-grid">
          <ComparisonCard
            title="Normal Commerce"
            score={normalScenario.score}
            level={normalScenario.level}
            action={normalScenario.action}
            active={scenario === 'normal'}
            onClick={() => runScenario('normal')}
          />

          <ComparisonCard
            title="Inventory Cornering Attack"
            score={attackData.score}
            level={attackData.level}
            action={attackData.action}
            active={scenario === 'attack'}
            onClick={() => runScenario('attack')}
          />
        </section>

        <section className="how-section">
          <div className="section-title">
            <div>
              <h2>How AgentShield Works</h2>
              <p>Detect → Score → Decide → Protect</p>
            </div>
          </div>

          <div className="flow-grid">
            <FlowCard
              number="01"
              title="Detect"
              text="Measure velocity, synchronization, inventory pressure and behavioral similarity."
            />

            <FlowCard
              number="02"
              title="Score"
              text="Combine the risk signals into a collective risk score from 0 to 100."
            />

            <FlowCard
              number="03"
              title="Decide"
              text="Classify the situation as LOW, MEDIUM, HIGH or CRITICAL."
            />

            <FlowCard
              number="04"
              title="Protect"
              text="Apply appropriate controls such as monitoring, challenge or inventory protection."
            />
          </div>
        </section>

        <footer>
          AgentShield identifies potential collective inventory risk.
          <br />
          A high risk score does not by itself prove malicious behavior.
        </footer>
      </main>
    </div>
  )
}

function SignalCard({ title, value, description }) {
  return (
    <div className="signal-card">
      <div className="signal-top">
        <span>{title}</span>
        <strong>{value}</strong>
      </div>

      <div className="progress">
        <div
          className="progress-fill"
          style={{ width: `${value}%` }}
        ></div>
      </div>

      <p>{description}</p>
    </div>
  )
}

function Metric({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function ComparisonCard({
  title,
  score,
  level,
  action,
  active,
  onClick,
}) {
  return (
    <button
      className={`comparison-card ${active ? 'selected' : ''}`}
      onClick={onClick}
    >
      <span>{title}</span>

      <strong>
        {score}
        <small>/100</small>
      </strong>

      <div className={`comparison-level ${level.toLowerCase()}`}>
        {level}
      </div>

      <p>{action}</p>
    </button>
  )
}

function FlowCard({ number, title, text }) {
  return (
    <div className="flow-card">
      <span className="flow-number">{number}</span>
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  )
}

export default App
