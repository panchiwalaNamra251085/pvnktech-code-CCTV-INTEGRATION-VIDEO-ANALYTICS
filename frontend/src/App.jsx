import { useEffect, useMemo, useRef, useState } from 'react'

const emptyCamera = { site_id: '', name: '', code: '', rtsp_url: '', description: '', is_active: true }
const emptySite = { name: '', code: '', description: '', latitude: '', longitude: '' }

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || `Request failed (${response.status})`)
  }
  return response.status === 204 ? null : response.json()
}

function StatusDot({ active }) {
  return <span className={`status-dot ${active ? 'is-live' : 'is-muted'}`} />
}

function App() {
  const [cameras, setCameras] = useState([])
  const [sites, setSites] = useState([])
  const [backendOnline, setBackendOnline] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [activeView, setActiveView] = useState('overview')
  const [demoCameraActive, setDemoCameraActive] = useState(false)
  const [demoCameraError, setDemoCameraError] = useState('')
  const [cameraForm, setCameraForm] = useState(emptyCamera)
  const [siteForm, setSiteForm] = useState(emptySite)
  const [showCameraForm, setShowCameraForm] = useState(false)
  const [showSiteForm, setShowSiteForm] = useState(false)
  const [editingCamera, setEditingCamera] = useState(null)
  const [testingId, setTestingId] = useState(null)
  const [search, setSearch] = useState('')
  const demoVideoRef = useRef(null)
  const demoStreamRef = useRef(null)

  useEffect(() => () => {
    demoStreamRef.current?.getTracks().forEach((track) => track.stop())
  }, [])

  useEffect(() => {
    if (demoCameraActive && demoVideoRef.current && demoStreamRef.current) {
      demoVideoRef.current.srcObject = demoStreamRef.current
      demoVideoRef.current.play().catch(() => {})
    }
  }, [demoCameraActive])

  async function startDemoCamera() {
    setDemoCameraError('')
    if (!navigator.mediaDevices?.getUserMedia) {
      setDemoCameraError('Camera access is not supported in this browser.')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      })
      demoStreamRef.current = stream
      setDemoCameraActive(true)
    } catch (cameraError) {
      setDemoCameraError(cameraError.name === 'NotAllowedError' ? 'Camera permission was denied.' : 'Unable to open the device camera.')
    }
  }

  function stopDemoCamera() {
    demoStreamRef.current?.getTracks().forEach((track) => track.stop())
    demoStreamRef.current = null
    if (demoVideoRef.current) demoVideoRef.current.srcObject = null
    setDemoCameraActive(false)
  }

  async function loadData() {
    setLoading(true)
    setError('')
    try {
      const [cameraData, siteData, health] = await Promise.all([
        request('/api/v1/cameras'),
        request('/api/v1/sites'),
        request('/health'),
      ])
      setCameras(cameraData)
      setSites(siteData)
      setBackendOnline(health.status === 'healthy')
    } catch (loadError) {
      setBackendOnline(false)
      setError(loadError.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [])

  const filteredCameras = useMemo(() => {
    const term = search.trim().toLowerCase()
    if (!term) return cameras
    return cameras.filter((camera) => [camera.name, camera.code, camera.rtsp_url].some((value) => value?.toLowerCase().includes(term)))
  }, [cameras, search])

  const activeCameras = cameras.filter((camera) => camera.is_active).length
  const testedCameras = cameras.filter((camera) => camera.lastTest?.connected).length

  async function createSite(event) {
    event.preventDefault()
    try {
      const payload = { ...siteForm, latitude: siteForm.latitude === '' ? null : Number(siteForm.latitude), longitude: siteForm.longitude === '' ? null : Number(siteForm.longitude) }
      const site = await request('/api/v1/sites', { method: 'POST', body: JSON.stringify(payload) })
      setSites((current) => [...current, site])
      setSiteForm(emptySite)
      setShowSiteForm(false)
      setNotice('Site created successfully')
    } catch (formError) { setError(formError.message) }
  }

  function openCameraForm(camera = null) {
    setEditingCamera(camera)
    setCameraForm(camera ? {
      site_id: String(camera.site_id),
      name: camera.name,
      code: camera.code,
      rtsp_url: camera.rtsp_url,
      description: camera.description || '',
      is_active: camera.is_active,
    } : emptyCamera)
    setShowCameraForm(true)
  }

  function closeCameraForm() {
    setShowCameraForm(false)
    setEditingCamera(null)
    setCameraForm(emptyCamera)
  }

  async function saveCamera(event) {
    event.preventDefault()
    try {
      const payload = { ...cameraForm, site_id: Number(cameraForm.site_id) }
      const camera = await request(editingCamera ? `/api/v1/cameras/${editingCamera.id}` : '/api/v1/cameras', {
        method: editingCamera ? 'PUT' : 'POST',
        body: JSON.stringify(payload),
      })
      setCameras((current) => editingCamera
        ? current.map((item) => item.id === camera.id ? { ...camera, lastTest: item.lastTest } : item)
        : [...current, camera])
      closeCameraForm()
      setNotice(editingCamera ? 'Camera updated successfully' : 'Camera added successfully')
    } catch (formError) { setError(formError.message) }
  }

  async function testCamera(camera) {
    setTestingId(camera.id)
    setError('')
    try {
      const result = await request(`/api/v1/cameras/${camera.id}/test`, { method: 'POST' })
      setCameras((current) => current.map((item) => item.id === camera.id ? { ...item, lastTest: result } : item))
      setNotice(result.connected ? `${camera.name} is receiving video` : `${camera.name} could not receive video`)
    } catch (testError) { setError(testError.message) } finally { setTestingId(null) }
  }

  async function deleteCamera(camera) {
    if (!window.confirm(`Remove ${camera.name}?`)) return
    try {
      await request(`/api/v1/cameras/${camera.id}`, { method: 'DELETE' })
      setCameras((current) => current.filter((item) => item.id !== camera.id))
      setNotice('Camera removed')
    } catch (deleteError) { setError(deleteError.message) }
  }

  const siteName = (siteId) => sites.find((site) => site.id === siteId)?.name || 'Unassigned'

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">C</span><span><strong>CCTV</strong><small>OPS CONSOLE</small></span></div>
        <div className="side-label">CONTROL ROOM</div>
        <nav>
          <button className={activeView === 'overview' ? 'nav-item active' : 'nav-item'} onClick={() => setActiveView('overview')}><span>01</span> Overview</button>
          <button className={activeView === 'cameras' ? 'nav-item active' : 'nav-item'} onClick={() => setActiveView('cameras')}><span>02</span> Cameras <b>{cameras.length}</b></button>
          <button className={activeView === 'sites' ? 'nav-item active' : 'nav-item'} onClick={() => setActiveView('sites')}><span>03</span> Sites <b>{sites.length}</b></button>
          <button className={activeView === 'demo-camera' ? 'nav-item active' : 'nav-item'} onClick={() => setActiveView('demo-camera')}><span>04</span> Device camera</button>
        </nav>
        <div className="sidebar-bottom"><div className="system-state"><StatusDot active={backendOnline} /><span>{backendOnline ? 'Backend online' : 'Backend offline'}</span></div><a href="/docs" target="_blank" rel="noreferrer">API documentation <span>↗</span></a></div>
      </aside>

      <main className="content">
        <header className="topbar"><div><p className="eyebrow">FIELD OPERATIONS / 04 SEPTEMBER 2026</p><h1>{activeView === 'overview' ? 'Good morning, operator.' : activeView === 'cameras' ? 'Camera inventory' : activeView === 'sites' ? 'Site directory' : 'Device camera demo'}</h1></div><div className="top-actions"><span className="connection"><StatusDot active={backendOnline} /> {backendOnline ? 'LIVE SYSTEM' : 'OFFLINE'}</span><button className="icon-button" title="Refresh data" onClick={loadData}>↻</button></div></header>
        {(error || notice) && <div className={error ? 'flash error' : 'flash'}>{error || notice}<button onClick={() => { setError(''); setNotice('') }}>×</button></div>}

        {activeView === 'overview' && <>
          <section className="hero-strip"><div><span className="kicker">NETWORK SNAPSHOT</span><h2>Every feed, one clear view.</h2><p>Monitor camera readiness, validate RTSP feeds, and keep every site accounted for.</p></div><div className="hero-signal"><span className="signal-ring"><span /></span><div><strong>{backendOnline ? 'Operational' : 'Disconnected'}</strong><small>API health status</small></div></div></section>
          <section className="metric-grid"><div className="metric-card"><span className="metric-label">TOTAL CAMERAS</span><strong>{cameras.length.toString().padStart(2, '0')}</strong><small>Registered endpoints</small></div><div className="metric-card accent"><span className="metric-label">ACTIVE CAMERAS</span><strong>{activeCameras.toString().padStart(2, '0')}</strong><small>{cameras.length ? Math.round(activeCameras / cameras.length * 100) : 0}% of inventory</small></div><div className="metric-card"><span className="metric-label">SITES</span><strong>{sites.length.toString().padStart(2, '0')}</strong><small>Managed locations</small></div><div className="metric-card"><span className="metric-label">LAST TESTS</span><strong>{testedCameras.toString().padStart(2, '0')}</strong><small>Successful in this session</small></div></section>
          <section className="section-heading"><div><span className="kicker">MONITORING QUEUE</span><h2>Camera readiness</h2></div><button className="text-button" onClick={() => setActiveView('cameras')}>View all cameras <span>→</span></button></section>
          <CameraTable cameras={filteredCameras.slice(0, 5)} siteName={siteName} testCamera={testCamera} testingId={testingId} deleteCamera={deleteCamera} editCamera={openCameraForm} loading={loading} />
        </>}

        {activeView === 'cameras' && <><div className="view-toolbar"><div className="search-box"><span>⌕</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search cameras, codes, or RTSP URLs" /></div><button className="primary-button" onClick={() => openCameraForm()}>+ Add camera</button></div><CameraTable cameras={filteredCameras} siteName={siteName} testCamera={testCamera} testingId={testingId} deleteCamera={deleteCamera} editCamera={openCameraForm} loading={loading} /></>}

        {activeView === 'sites' && <><div className="view-toolbar"><div><span className="kicker">LOCATIONS</span><h2>Managed sites</h2></div><button className="primary-button" onClick={() => setShowSiteForm(true)}>+ Add site</button></div><div className="site-grid">{sites.map((site) => <article className="site-card" key={site.id}><div className="site-card-top"><span className="site-index">SITE / {String(site.id).padStart(2, '0')}</span><StatusDot active={site.is_active} /></div><h3>{site.name}</h3><p>{site.description || 'No description provided.'}</p><div className="site-meta"><span>{site.code || 'NO CODE'}</span><span>{cameras.filter((camera) => camera.site_id === site.id).length} cameras</span></div></article>)}{!loading && sites.length === 0 && <EmptyState label="No sites registered yet" />}</div></>}
        {activeView === 'demo-camera' && <DemoCamera videoRef={demoVideoRef} active={demoCameraActive} error={demoCameraError} onStart={startDemoCamera} onStop={stopDemoCamera} />}
      </main>

      {showCameraForm && <Modal title={editingCamera ? 'Edit camera' : 'Register camera'} onClose={closeCameraForm}><form onSubmit={saveCamera}><Field label="Camera name" value={cameraForm.name} onChange={(value) => setCameraForm({ ...cameraForm, name: value })} required /><Field label="Camera code" value={cameraForm.code} onChange={(value) => setCameraForm({ ...cameraForm, code: value })} required /><label className="field"><span>Site</span><select value={cameraForm.site_id} onChange={(event) => setCameraForm({ ...cameraForm, site_id: event.target.value })} required><option value="">Select a site</option>{sites.map((site) => <option key={site.id} value={site.id}>{site.name}</option>)}</select></label><Field label="RTSP URL" value={cameraForm.rtsp_url} onChange={(value) => setCameraForm({ ...cameraForm, rtsp_url: value })} required /><Field label="Description" value={cameraForm.description} onChange={(value) => setCameraForm({ ...cameraForm, description: value })} /><label className="checkbox-field"><input type="checkbox" checked={cameraForm.is_active} onChange={(event) => setCameraForm({ ...cameraForm, is_active: event.target.checked })} /><span>Camera is active</span></label><FormActions onCancel={closeCameraForm} /></form></Modal>}
      {showSiteForm && <Modal title="Add managed site" onClose={() => setShowSiteForm(false)}><form onSubmit={createSite}><Field label="Site name" value={siteForm.name} onChange={(value) => setSiteForm({ ...siteForm, name: value })} required /><Field label="Site code" value={siteForm.code} onChange={(value) => setSiteForm({ ...siteForm, code: value })} /><Field label="Description" value={siteForm.description} onChange={(value) => setSiteForm({ ...siteForm, description: value })} /><div className="two-fields"><Field label="Latitude" type="number" value={siteForm.latitude} onChange={(value) => setSiteForm({ ...siteForm, latitude: value })} /><Field label="Longitude" type="number" value={siteForm.longitude} onChange={(value) => setSiteForm({ ...siteForm, longitude: value })} /></div><FormActions onCancel={() => setShowSiteForm(false)} /></form></Modal>}
    </div>
  )
}

function CameraTable({ cameras, siteName, testCamera, testingId, deleteCamera, editCamera, loading }) {
  if (loading) return <div className="empty-state"><span className="loader" />Loading live inventory...</div>
  if (!cameras.length) return <EmptyState label="No cameras match this view" />
  return <div className="table-wrap"><table><thead><tr><th>CAMERA</th><th>SITE</th><th>STATE</th><th>LAST CHECK</th><th /></tr></thead><tbody>{cameras.map((camera) => { const result = camera.lastTest; return <tr key={camera.id}><td><div className="camera-name"><span className="camera-icon">◉</span><span><strong>{camera.name}</strong><small>{camera.code}</small></span></div></td><td>{siteName(camera.site_id)}</td><td><span className={`status-pill ${camera.is_active ? 'active' : 'inactive'}`}><StatusDot active={camera.is_active} />{camera.is_active ? 'Active' : 'Inactive'}</span></td><td>{result ? <span className={result.connected ? 'test-result good' : 'test-result bad'}>{result.connected ? `Video ${result.width}×${result.height}` : 'No signal'}</span> : <span className="muted">Not tested</span>}</td><td><div className="row-actions"><button className="small-button" onClick={() => editCamera(camera)}>Edit</button><button className="small-button" onClick={() => testCamera(camera)} disabled={testingId === camera.id}>{testingId === camera.id ? 'Testing...' : 'Test feed'}</button><button className="delete-button" title="Delete camera" onClick={() => deleteCamera(camera)}>×</button></div></td></tr>})}</tbody></table></div>
}

function Field({ label, value, onChange, type = 'text', required = false }) { return <label className="field"><span>{label}</span><input type={type} value={value} onChange={(event) => onChange(event.target.value)} required={required} /></label> }
function FormActions({ onCancel }) { return <div className="form-actions"><button type="button" className="secondary-button" onClick={onCancel}>Cancel</button><button type="submit" className="primary-button">Save</button></div> }
function Modal({ title, children, onClose }) { return <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><div className="modal"><div className="modal-header"><div><span className="kicker">CONFIGURATION</span><h2>{title}</h2></div><button className="close-button" onClick={onClose}>×</button></div>{children}</div></div> }
function EmptyState({ label }) { return <div className="empty-state"><span className="empty-mark">—</span>{label}</div> }

function DemoCamera({ videoRef, active, error, onStart, onStop }) {
  return <section className="demo-camera"><div className="section-heading"><div><span className="kicker">LOCAL DEVICE TEST</span><h2>Test laptop or mobile camera</h2><p className="demo-copy">Use this demo to confirm that the browser can access a nearby camera.</p></div><span className="status-pill"><StatusDot active={active} />{active ? 'Camera live' : 'Camera stopped'}</span></div><div className="camera-preview">{active ? <video ref={videoRef} autoPlay playsInline muted /> : <div className="preview-placeholder"><span className="camera-icon">◉</span><strong>Camera preview</strong><small>Press start and allow camera permission</small></div>}</div>{error && <div className="flash error demo-error">{error}</div>}<div className="demo-actions">{active ? <button className="secondary-button" onClick={onStop}>Stop camera</button> : <button className="primary-button" onClick={onStart}>Start camera test</button>}<span className="muted">No video is uploaded or stored.</span></div></section>
}

export default App
