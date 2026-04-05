import { useState, useEffect, useCallback, useRef } from 'react'

const API = ''  // Vite proxy → localhost:5000

// ── Constants ─────────────────────────────────────────────────────────────────
const AUTO_REFRESH_SECONDS = 30

// Commands that suggest malicious intent — colour-coded in the commands panel
const DANGER_PATTERNS = new RegExp('wget|curl|chmod|crontab|tmp|base64|eval|mkfifo|python|bash|payload|exploit|ransom', 'i')
const WARN_PATTERNS   = new RegExp('shadow|passwd|sudoers|cred', 'i')
const INFO_PATTERNS   = new RegExp('uname|whoami|hostname|ifconfig|ps aux|netstat', 'i')

// ── SVG Icon Library ─────────────────────────────────────────────────────────
const Icons = {
  Shield: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
    </svg>
  ),
  Alert: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <line x1="12" y1="8" x2="12" y2="12"/>
      <line x1="12" y1="16" x2="12.01" y2="16"/>
    </svg>
  ),
  Globe: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <line x1="2" y1="12" x2="22" y2="12"/>
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
    </svg>
  ),
  Lock: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
      <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
    </svg>
  ),
  Target: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <circle cx="12" cy="12" r="6"/>
      <circle cx="12" cy="12" r="2"/>
    </svg>
  ),
  Terminal: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="4 17 10 11 4 5"/>
      <line x1="12" y1="19" x2="20" y2="19"/>
    </svg>
  ),
  Brain: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z"/>
      <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z"/>
    </svg>
  ),
  Signal: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
    </svg>
  ),
  Search: () => (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8"/>
      <line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>
  ),
  Refresh: () => (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23 4 23 10 17 10"/>
      <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
    </svg>
  ),
  User: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
      <circle cx="12" cy="7" r="4"/>
    </svg>
  ),
  Warning: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
      <line x1="12" y1="9" x2="12" y2="13"/>
      <line x1="12" y1="17" x2="12.01" y2="17"/>
    </svg>
  ),
  Bolt: () => (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
    </svg>
  ),
  Check: () => (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12"/>
    </svg>
  ),
  Copy: () => (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
    </svg>
  ),
  Skull: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a9 9 0 0 0-9 9c0 3.18 1.66 6 4.23 7.62V20a1 1 0 0 0 1 1h7.54a1 1 0 0 0 1-1v-1.38C19.34 17 21 14.18 21 11a9 9 0 0 0-9-9z"/>
      <line x1="9" y1="16" x2="9.01" y2="16"/>
      <line x1="15" y1="16" x2="15.01" y2="16"/>
    </svg>
  ),
  Info: () => (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <line x1="12" y1="16" x2="12" y2="12"/>
      <line x1="12" y1="8" x2="12.01" y2="8"/>
    </svg>
  ),
  Logo: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/>
    </svg>
  ),
  Wifi: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12.55a11 11 0 0 1 14.08 0"/>
      <path d="M1.42 9a16 16 0 0 1 21.16 0"/>
      <path d="M8.53 16.11a6 16 0 0 1 6.95 0"/>
      <line x1="12" y1="20" x2="12.01" y2="20"/>
    </svg>
  ),
}

// ── Data hooks ─────────────────────────────────────────────────────────────────

function useSessions() {
  const [sessions, setSessions]       = useState([])
  const [allLogs, setAllLogs]         = useState([])
  const [loading, setLoading]         = useState(true)
  const [lastRefresh, setLastRefresh] = useState(null)

  const fetch_ = useCallback(async () => {
    setLoading(true)
    try {
      const [sRes, lRes] = await Promise.all([
        fetch(`${API}/api/sessions?limit=50`).then(r => r.json()),
        fetch(`${API}/api/logs?limit=200`).then(r => r.json()),
      ])
      setSessions(sRes.data || [])
      setAllLogs(lRes.data || [])
      setLastRefresh(new Date())
    } catch {
      setSessions([])
      setAllLogs([])
    }
    setLoading(false)
  }, [])

  useEffect(() => { fetch_() }, [fetch_])
  return { sessions, allLogs, loading, refresh: fetch_, lastRefresh }
}

function useActivity(session) {
  const [activity, setActivity] = useState([])
  const [loading, setLoading]   = useState(false)

  useEffect(() => {
    if (!session) { setActivity([]); return }
    const sessionId = session.session_id
    const sourceIp  = session.source_ip
    setLoading(true)

    Promise.all([
      fetch(`${API}/api/sessions/${sessionId}/commands`).then(r => r.json()),
      fetch(`${API}/api/logs?limit=100${sourceIp ? `&ip=${encodeURIComponent(sourceIp)}` : ''}`).then(r => r.json()),
    ]).then(([cmds, logs]) => {
      const cmdItems = (cmds.data || []).map(c => ({
        type: 'cmd', time: c.timestamp, text: c.command, id: `cmd-${c.id}`,
      }))
      const logItems = (logs.data || [])
        .filter(l => !sourceIp || l.source_ip === sourceIp)
        .map(l => ({ type: 'http', time: l.timestamp, text: l.attack_type, id: `log-${l.id}` }))
      const merged = [...cmdItems, ...logItems].sort((a, b) => new Date(b.time) - new Date(a.time))
      setActivity(merged)
    }).catch(() => setActivity([])).finally(() => setLoading(false))
  }, [session?.session_id, session?.source_ip])

  return { activity, loading }
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function fmtTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z')
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function fmtRefresh(date) {
  if (!date) return '—'
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function cmdClass(cmd) {
  if (DANGER_PATTERNS.test(cmd)) return 'danger'
  if (WARN_PATTERNS.test(cmd))   return 'warn'
  if (INFO_PATTERNS.test(cmd))   return 'info'
  return ''
}

function threatLevel(session) {
  if (session.success === 1) return 'critical'
  if (session.username)      return 'medium'
  return 'low'
}

function skillClass(level) {
  if (!level) return ''
  const l = level.toLowerCase()
  if (l === 'nation-state') return 'skill-nation-state'
  if (l === 'high')         return 'skill-high'
  if (l === 'medium')       return 'skill-medium'
  return 'skill-low'
}

function getAttackTypeFreq(logs) {
  const freq = {}
  ;(logs || []).forEach(l => {
    if (l.attack_type) freq[l.attack_type] = (freq[l.attack_type] || 0) + 1
  })
  return Object.entries(freq).sort((a, b) => b[1] - a[1]).slice(0, 5)
}

// ── Toast Hook ─────────────────────────────────────────────────────────────────

function useToast() {
  const [toasts, setToasts] = useState([])

  const push = useCallback((msg, type = 'info') => {
    const id = Date.now()
    setToasts(t => [...t, { id, msg, type }])
    setTimeout(() => {
      setToasts(t => t.map(x => x.id === id ? { ...x, hiding: true } : x))
      setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 260)
    }, 3000)
  }, [])

  return { toasts, push }
}

// ── Toast Container ────────────────────────────────────────────────────────────

function Toasts({ toasts }) {
  return (
    <div className="toast-container">
      {toasts.map(t => (
        <div key={t.id} className={`toast ${t.type} ${t.hiding ? 'hiding' : ''}`}>
          <span className="toast-icon">
            {t.type === 'success' ? <Icons.Check /> : t.type === 'error' ? <Icons.Warning /> : <Icons.Info />}
          </span>
          {t.msg}
        </div>
      ))}
    </div>
  )
}

// ── Stats Bar ─────────────────────────────────────────────────────────────────

function StatsBar({ sessions, allLogs }) {
  const totalAttacks = allLogs.length
  const uniqueIPs    = new Set([
    ...sessions.map(s => s.source_ip),
    ...allLogs.map(l => l.source_ip).filter(Boolean),
  ]).size
  const authBreaches = sessions.filter(s => s.success === 1).length

  const topService = (() => {
    const f = {}
    allLogs.forEach(l => { if (l.attack_type) f[l.attack_type] = (f[l.attack_type] || 0) + 1 })
    const top = Object.entries(f).sort((a, b) => b[1] - a[1])[0]
    return top ? top[0].replace(/_/g, ' ').replace('scan', '').trim() : '—'
  })()

  return (
    <div className="stats-bar">
      <div className="stat-card">
        <div className="stat-icon teal"><Icons.Shield /></div>
        <div className="stat-info">
          <div className="stat-label">Sessions</div>
          <div className="stat-num teal">{sessions.length}</div>
        </div>
      </div>
      <div className="stat-card">
        <div className="stat-icon red"><Icons.Alert /></div>
        <div className="stat-info">
          <div className="stat-label">Total Attacks</div>
          <div className="stat-num red">{totalAttacks}</div>
        </div>
      </div>
      <div className="stat-card">
        <div className="stat-icon yellow"><Icons.Globe /></div>
        <div className="stat-info">
          <div className="stat-label">Unique IPs</div>
          <div className="stat-num yellow">{uniqueIPs}</div>
        </div>
      </div>
      <div className="stat-card">
        <div className="stat-icon purple"><Icons.Lock /></div>
        <div className="stat-info">
          <div className="stat-label">Auth Breaches</div>
          <div className="stat-num purple">{authBreaches}</div>
        </div>
      </div>
      <div className="stat-card">
        <div className="stat-icon blue"><Icons.Target /></div>
        <div className="stat-info">
          <div className="stat-label">Top Attack</div>
          <div className="stat-num blue" style={{ fontSize: 11, lineHeight: 1.3, marginTop: 2 }}>
            {topService || '—'}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Attacker List ─────────────────────────────────────────────────────────────

function AttackerList({ sessions, loading, selected, onSelect, onRefresh, refreshing }) {
  const [query, setQuery] = useState('')

  const filtered = sessions.filter(s =>
    !query ||
    s.source_ip.includes(query) ||
    (s.username || '').toLowerCase().includes(query.toLowerCase())
  )

  return (
    <div className="sidebar">
      {/* Header */}
      <div className="panel-header">
        <div className="panel-title">
          <span className="panel-title-icon"><Icons.Target /></span>
          Attackers
        </div>
        <div className="panel-actions">
          <span className="badge">{sessions.length}</span>
          <button
            className={`refresh-btn ${refreshing ? 'spinning' : ''}`}
            onClick={onRefresh}
            title="Refresh"
          >
            <span className="refresh-icon"><Icons.Refresh /></span>
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="search-wrap">
        <div className="search-wrap-inner">
          <span className="search-icon"><Icons.Search /></span>
          <input
            className="search-input"
            placeholder="Search IP or username…"
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
        </div>
      </div>

      {/* List */}
      <div className="panel-body">
        {loading ? (
          <div className="loader"><div className="spinner" /></div>
        ) : filtered.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon"><Icons.User /></div>
            <div className="empty-title">{query ? 'No match' : 'No attackers yet'}</div>
            <div className="empty-sub">
              {query ? 'Try a different search.' : 'Start the honeypot and wait for connections.'}
            </div>
          </div>
        ) : (
          <ul className="attacker-list">
            {filtered.map(s => {
              const level = threatLevel(s)
              return (
                <li
                  key={s.session_id}
                  className={`attacker-item ${selected === s.session_id ? 'active' : ''}`}
                  onClick={() => onSelect(s.session_id)}
                >
                  <div className={`attacker-avatar avatar-${level}`}>
                    {level === 'critical' ? <Icons.Skull /> : <Icons.User />}
                  </div>
                  <div className="attacker-info">
                    <div className="attacker-ip">{s.source_ip}</div>
                    <div className="attacker-sub">
                      <div className={`threat-dot ${level}`} />
                      <span className="attacker-cred">
                        {s.username ? `${s.username} / ${s.password || '?'}` : 'HTTP scan'}
                      </span>
                    </div>
                  </div>
                  <span className={`threat-pill ${level}`}>
                    {level === 'critical' ? (
                      <><Icons.Check /> AUTH</>
                    ) : level}
                  </span>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}

// ── Attack Type Mini Chart ────────────────────────────────────────────────────

function AttackTypeChart({ logs }) {
  const entries = getAttackTypeFreq(logs)
  const max = entries[0]?.[1] || 1
  if (!entries.length) return null

  return (
    <div className="atk-chart-section">
      <div className="atk-chart-title">Attack Distribution</div>
      <div className="atk-bar-wrap">
        {entries.map(([type, count]) => (
          <div key={type} className="atk-bar-row">
            <div className="atk-bar-label">{type.replace(/_/g, ' ')}</div>
            <div className="atk-bar-track">
              <div className="atk-bar-fill" style={{ width: `${(count / max) * 100}%` }} />
            </div>
            <div className="atk-bar-count">{count}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Profile Panel – AI ────────────────────────────────────────────────────────

function ProfilePanel({ sessionId, sessions, toast }) {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const [meta, setMeta]       = useState(null)

  useEffect(() => { setProfile(null); setError(null); setMeta(null) }, [sessionId])

  const session = sessions.find(s => s.session_id === sessionId)

  async function analyze() {
    setLoading(true); setError(null)
    try {
      const r = await fetch(`${API}/ai/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ip: session?.source_ip, limit: 50 }),
      })
      const j = await r.json()
      if (j.status === 'error') throw new Error(j.message)
      setProfile(j.profile)
      setMeta({ reduction: j.token_reduction_pct, ips: j.unique_ips_analyzed })
      toast(`Analysis complete — ${j.token_reduction_pct?.toFixed(0)}% token savings`, 'success')
    } catch (e) {
      setError(e.message)
      toast('Gemini analysis failed', 'error')
    }
    setLoading(false)
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <div className="panel-title">
          <span className="panel-title-icon"><Icons.Brain /></span>
          AI Threat Profile
        </div>
        {meta && (
          <div className="ai-reduction-badge">
            <Icons.Bolt /> {meta.reduction?.toFixed(0)}% saved
          </div>
        )}
      </div>

      <div className="ai-panel-body panel-body" style={{ overflow: 'auto' }}>
        {!sessionId ? (
          <div className="empty-state">
            <div className="empty-icon"><Icons.Brain /></div>
            <div className="empty-title">No session selected</div>
            <div className="empty-sub">Pick an attacker to run Gemini analysis.</div>
          </div>
        ) : (
          <>
            <button className="analyze-btn" onClick={analyze} disabled={loading}>
              {loading ? (
                <><div className="spinner" style={{ width: 13, height: 13 }} /> Analyzing…</>
              ) : (
                <><Icons.Bolt /> Analyze with Gemini</>
              )}
            </button>

            {error && (
              <div className="ai-error">
                <Icons.Warning />
                <span>{error}</span>
              </div>
            )}

            {profile && !loading && !profile.error && (
              <div className="profile-grid">
                <div className="profile-field">
                  <div className="profile-label">Attacker Type</div>
                  <div className="profile-value">{profile.attacker_type || '—'}</div>
                </div>
                <div className="profile-field">
                  <div className="profile-label">Skill Level</div>
                  <span className={`skill-pill ${skillClass(profile.skill_level)}`}>
                    {profile.skill_level || '—'}
                  </span>
                </div>
                <div className="profile-field">
                  <div className="profile-label">Intent</div>
                  <div className="profile-value">{profile.intent || '—'}</div>
                </div>
                {(profile.tools_likely_used || []).length > 0 && (
                  <div className="profile-field">
                    <div className="profile-label">Tools / Techniques</div>
                    <div className="tools-list">
                      {profile.tools_likely_used.map(t => (
                        <span key={t} className="tool-chip">{t}</span>
                      ))}
                    </div>
                  </div>
                )}
                {profile.summary && (
                  <div className="profile-field">
                    <div className="profile-label">Summary</div>
                    <p className="profile-summary">{profile.summary}</p>
                  </div>
                )}
              </div>
            )}

            {profile?.error && (
              <div className="ai-error">
                <Icons.Warning />
                <span>{profile.error}</span>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// ── Timeline ──────────────────────────────────────────────────────────────────

function Timeline({ sessionId, activity, loading, sessions }) {
  const session = sessions.find(s => s.session_id === sessionId)

  const events = []
  if (session) {
    events.push({
      type: 'login',
      time: session.start_time,
      text: 'Session started',
      detail: `${session.source_ip} · ${session.username || 'anon'}`,
      id: 'session-start',
    })
    if (session.end_time) {
      const dur = Math.round((new Date(session.end_time) - new Date(session.start_time)) / 1000)
      events.push({
        type: 'login',
        time: session.end_time,
        text: 'Session closed',
        detail: `Duration: ${dur}s`,
        id: 'session-end',
      })
    }
  }

  const all = [...events, ...activity].sort((a, b) => new Date(a.time) - new Date(b.time))

  const nodeClass = (type) =>
    type === 'cmd' ? 'tl-cmd' : type === 'login' ? 'tl-login' : 'tl-http'

  return (
    <div className="timeline-panel">
      <div className="panel-header">
        <div className="panel-title">
          <span className="panel-title-icon"><Icons.Signal /></span>
          Attack Timeline
        </div>
        <span className="badge">{all.length}</span>
      </div>

      <div className="timeline-body">
        {!sessionId ? (
          <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '18px 0', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Icons.Signal /> Select an attacker to view their attack timeline.
          </div>
        ) : loading ? (
          <div className="loader" style={{ padding: 16 }}><div className="spinner" /></div>
        ) : all.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '18px 0' }}>No timeline events.</div>
        ) : (
          <div className="timeline-track">
            {all.map(ev => (
              <div key={ev.id} className="tl-event-card">
                <div className={`tl-node ${nodeClass(ev.type)}`}>
                  <div className="tl-node-inner" />
                </div>
                <div className="tl-card-body">
                  <div className="tl-card-time">{fmtTime(ev.time)}</div>
                  <div className="tl-card-text">{ev.text}</div>
                  <span className={`tl-type-tag ${nodeClass(ev.type)}`}>{ev.type}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Auto-Refresh Progress Bar ─────────────────────────────────────────────────

function AutoRefreshBar({ lastRefresh, onRefresh, interval = AUTO_REFRESH_SECONDS }) {
  const [progress, setProgress] = useState(100)
  const startRef = useRef(Date.now())

  useEffect(() => {
    startRef.current = Date.now()
    setProgress(100)
  }, [lastRefresh])

  useEffect(() => {
    const tick = setInterval(() => {
      const elapsed  = (Date.now() - startRef.current) / 1000
      const remaining = Math.max(0, interval - elapsed)
      setProgress((remaining / interval) * 100)
      if (remaining <= 0) {
        onRefresh()
        startRef.current = Date.now()
      }
    }, 500)
    return () => clearInterval(tick)
  }, [onRefresh, interval])

  return (
    <div className="refresh-bar" title={`Auto-refresh every ${interval}s`}>
      <div className="refresh-bar-fill" style={{ width: `${progress}%` }} />
    </div>
  )
}

// ── App ───────────────────────────────────────────────────────────────────────

export default function App() {
  const { sessions, allLogs, loading: sessLoading, refresh, lastRefresh } = useSessions()
  const [selectedId, setSelectedId]   = useState(null)
  const [refreshing, setRefreshing]   = useState(false)
  const { toasts, push: toast }       = useToast()

  const selectedSession = sessions.find(s => s.session_id === selectedId) || null
  const { activity, loading: actLoading } = useActivity(selectedSession)

  // Auto-select first session
  useEffect(() => {
    if (!selectedId && sessions.length > 0) setSelectedId(sessions[0].session_id)
  }, [sessions, selectedId])

  const handleRefresh = useCallback(async () => {
    setRefreshing(true)
    await refresh()
    setRefreshing(false)
    toast('Data refreshed', 'success')
  }, [refresh, toast])

  const handleCopy = useCallback((text) => {
    navigator.clipboard?.writeText(text).then(
      () => toast('Copied to clipboard', 'success'),
      () => toast('Copy failed', 'error'),
    )
  }, [toast])

  const sessionLogs = allLogs.filter(
    l => !selectedSession || l.source_ip === selectedSession.source_ip
  )

  return (
    <div className="layout">

      {/* Topbar */}
      <header className="topbar">
        <div className="topbar-left">
          <div className="topbar-logo">
            <div className="logo-icon"><Icons.Logo /></div>
            MirrorTrap
          </div>
          <div className="live-badge">
            <div className="live-dot" /> LIVE
          </div>
        </div>

        <div className="topbar-right">
          <div className="topbar-stat">
            <div className="topbar-stat-label">Last Refresh</div>
            <div className="topbar-stat-value">{fmtRefresh(lastRefresh)}</div>
          </div>
          <div className="topbar-divider" />
          <div className="topbar-stat">
            <div className="topbar-stat-label">Auto-refresh</div>
            <div className="topbar-stat-value">{AUTO_REFRESH_SECONDS}s</div>
          </div>
          <div className="topbar-divider" />
          <div className="topbar-actions">
            <button className="icon-btn" onClick={handleRefresh} title="Refresh now">
              <Icons.Refresh />
            </button>
          </div>
        </div>
      </header>

      {/* Stats Bar */}
      <StatsBar sessions={sessions} allLogs={allLogs} />

      {/* Main Grid */}
      <div className="main">

        {/* Sidebar — attacker list */}
        <AttackerList
          sessions={sessions}
          loading={sessLoading}
          selected={selectedId}
          onSelect={setSelectedId}
          onRefresh={handleRefresh}
          refreshing={refreshing}
        />

        {/* Content */}
        <div className="content-area">

          {/* Shell Commands */}
          <div className="panel" style={{ gridColumn: 1, gridRow: 1 }}>
            <div className="panel-header">
              <div className="panel-title">
                <span className="panel-title-icon"><Icons.Terminal /></span>
                Shell Commands
              </div>
              <span className="badge">{activity.filter(a => a.type === 'cmd').length}</span>
            </div>
            {selectedSession && sessionLogs.length > 0 && (
              <AttackTypeChart logs={sessionLogs} />
            )}
            <div className="panel-body">
              {!selectedId ? (
                <div className="empty-state">
                  <div className="empty-icon"><Icons.Terminal /></div>
                  <div className="empty-title">Select an attacker</div>
                  <div className="empty-sub">Click a session from the left panel.</div>
                </div>
              ) : actLoading ? (
                <div className="loader"><div className="spinner" /></div>
              ) : activity.filter(a => a.type === 'cmd').length === 0 ? (
                <div className="empty-state">
                  <div className="empty-icon"><Icons.Terminal /></div>
                  <div className="empty-title">No SSH commands</div>
                  <div className="empty-sub">This attacker used HTTP only.</div>
                </div>
              ) : (
                <ul className="cmd-list">
                  {activity.filter(a => a.type === 'cmd').map(c => (
                    <li key={c.id} className="cmd-row">
                      <span className="cmd-time">{fmtTime(c.time)}</span>
                      <span className="cmd-prompt">$</span>
                      <span className={`cmd-text ${cmdClass(c.text)}`}>{c.text}</span>
                      <button className="cmd-copy" onClick={() => handleCopy(c.text)}>
                        <Icons.Copy />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* AI Profile */}
          <ProfilePanel
            sessionId={selectedId}
            sessions={sessions}
            toast={toast}
          />

          {/* Timeline */}
          <Timeline
            sessionId={selectedId}
            activity={activity}
            loading={actLoading}
            sessions={sessions}
          />
        </div>
      </div>

      {/* Auto-refresh bar */}
      <div style={{ position: 'fixed', top: 106, left: 0, right: 0, zIndex: 20 }}>
        <AutoRefreshBar lastRefresh={lastRefresh} onRefresh={handleRefresh} />
      </div>

      {/* Toasts */}
      <Toasts toasts={toasts} />
    </div>
  )
}
