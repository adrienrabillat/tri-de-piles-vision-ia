import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  BarChart, Bar, PieChart, Pie, Cell, ResponsiveContainer, AreaChart, Area
} from 'recharts';
import {
  Settings, Play, Camera, BarChart3, Upload, Zap, RefreshCw,
  CheckCircle, XCircle, Clock, Activity, Box, Eye, Layers,
  Cpu, Database, TrendingUp, AlertTriangle
} from 'lucide-react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// ============================================================
// STYLES
// ============================================================

const styles = {
  app: {
    fontFamily: "'Inter', -apple-system, sans-serif",
    background: '#0f1117',
    color: '#e4e4e7',
    minHeight: '100vh',
  },
  header: {
    background: 'linear-gradient(135deg, #1a1b2e 0%, #16213e 100%)',
    borderBottom: '1px solid #2a2d3e',
    padding: '16px 32px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  headerTitle: {
    fontSize: '20px',
    fontWeight: 700,
    background: 'linear-gradient(90deg, #60a5fa, #a78bfa)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
  },
  nav: {
    display: 'flex',
    gap: '4px',
    background: '#1a1b2e',
    borderRadius: '12px',
    padding: '4px',
  },
  navBtn: (active) => ({
    padding: '8px 16px',
    borderRadius: '8px',
    border: 'none',
    background: active ? '#3b82f6' : 'transparent',
    color: active ? '#fff' : '#94a3b8',
    cursor: 'pointer',
    fontSize: '13px',
    fontWeight: 500,
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    transition: 'all 0.2s',
  }),
  main: {
    padding: '24px 32px',
    maxWidth: '1400px',
    margin: '0 auto',
  },
  card: {
    background: '#1a1b2e',
    borderRadius: '16px',
    border: '1px solid #2a2d3e',
    padding: '24px',
    marginBottom: '20px',
  },
  cardTitle: {
    fontSize: '16px',
    fontWeight: 600,
    marginBottom: '16px',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  grid: (cols) => ({
    display: 'grid',
    gridTemplateColumns: `repeat(${cols}, 1fr)`,
    gap: '16px',
    marginBottom: '20px',
  }),
  stat: {
    background: '#1e1f35',
    borderRadius: '12px',
    padding: '16px',
    border: '1px solid #2a2d3e',
  },
  statLabel: {
    fontSize: '12px',
    color: '#94a3b8',
    marginBottom: '4px',
  },
  statValue: {
    fontSize: '24px',
    fontWeight: 700,
  },
  input: {
    background: '#0f1117',
    border: '1px solid #2a2d3e',
    borderRadius: '8px',
    padding: '8px 12px',
    color: '#e4e4e7',
    fontSize: '14px',
    width: '100%',
    outline: 'none',
  },
  label: {
    fontSize: '13px',
    color: '#94a3b8',
    marginBottom: '6px',
    display: 'block',
  },
  btnPrimary: {
    background: 'linear-gradient(135deg, #3b82f6, #6366f1)',
    color: '#fff',
    border: 'none',
    borderRadius: '10px',
    padding: '10px 20px',
    fontSize: '14px',
    fontWeight: 600,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  btnSecondary: {
    background: '#2a2d3e',
    color: '#e4e4e7',
    border: '1px solid #3a3d4e',
    borderRadius: '10px',
    padding: '10px 20px',
    fontSize: '14px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  toggle: (on) => ({
    width: '44px',
    height: '24px',
    borderRadius: '12px',
    background: on ? '#3b82f6' : '#2a2d3e',
    border: 'none',
    cursor: 'pointer',
    position: 'relative',
    transition: 'all 0.2s',
  }),
  toggleDot: (on) => ({
    width: '18px',
    height: '18px',
    borderRadius: '50%',
    background: '#fff',
    position: 'absolute',
    top: '3px',
    left: on ? '23px' : '3px',
    transition: 'all 0.2s',
  }),
  progress: {
    background: '#0f1117',
    borderRadius: '8px',
    height: '8px',
    overflow: 'hidden',
  },
  progressBar: (pct, color = '#3b82f6') => ({
    height: '100%',
    width: `${pct}%`,
    background: `linear-gradient(90deg, ${color}, ${color}cc)`,
    borderRadius: '8px',
    transition: 'width 0.5s ease',
  }),
  badge: (color) => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: '4px',
    padding: '4px 10px',
    borderRadius: '20px',
    fontSize: '12px',
    fontWeight: 500,
    background: `${color}20`,
    color: color,
  }),
};

const COLORS = ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#ef4444'];

// ============================================================
// TOGGLE COMPONENT
// ============================================================

function Toggle({ value, onChange }) {
  return (
    <button style={styles.toggle(value)} onClick={() => onChange(!value)}>
      <div style={styles.toggleDot(value)} />
    </button>
  );
}

// ============================================================
// CONFIGURATION PAGE
// ============================================================

function ConfigPage({ config, setConfig, onSave }) {
  const updateField = (key, value) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  return (
    <div>
      <div style={styles.card}>
        <div style={styles.cardTitle}><Settings size={18} /> Parametres de Generation</div>
        <div style={styles.grid(3)}>
          <div>
            <label style={styles.label}>Nombre d'images</label>
            <input style={styles.input} type="number" value={config.num_images || 100}
              onChange={e => updateField('num_images', parseInt(e.target.value))} />
          </div>
          <div>
            <label style={styles.label}>Moteur de rendu</label>
            <select style={styles.input} value={config.render_engine || 'BLENDER_EEVEE'}
              onChange={e => updateField('render_engine', e.target.value)}>
              <option value="BLENDER_EEVEE">EEVEE (Rapide)</option>
              <option value="CYCLES">Cycles (Photoreal)</option>
            </select>
          </div>
          <div>
            <label style={styles.label}>Seed aleatoire</label>
            <input style={styles.input} type="number" value={config.random_seed || 42}
              onChange={e => updateField('random_seed', parseInt(e.target.value))} />
          </div>
        </div>
        <div style={styles.grid(2)}>
          <div>
            <label style={styles.label}>Piles min/max par image</label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input style={styles.input} type="number" value={(config.battery_count_range || [3, 10])[0]}
                onChange={e => updateField('battery_count_range', [parseInt(e.target.value), (config.battery_count_range || [3, 10])[1]])} />
              <input style={styles.input} type="number" value={(config.battery_count_range || [3, 10])[1]}
                onChange={e => updateField('battery_count_range', [(config.battery_count_range || [3, 10])[0], parseInt(e.target.value)])} />
            </div>
          </div>
        </div>
      </div>

      <div style={styles.card}>
        <div style={styles.cardTitle}><Layers size={18} /> Domain Randomization V3</div>
        <div style={styles.grid(2)}>
          {[
            { key: 'advanced_textures_enabled', label: 'Textures PBR avancees (rayures, poussiere, usure)' },
            { key: 'distractors_enabled', label: 'Objets distracteurs (debris, vis, etiquettes)' },
            { key: 'camera_artifacts_enabled', label: 'Artefacts camera (vignetting, aberration, DOF)' },
            { key: 'mixed_rendering_enabled', label: 'Rendu mixte EEVEE/CYCLES (domain mixing)' },
          ].map(({ key, label }) => (
            <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px', background: '#0f1117', borderRadius: '8px' }}>
              <span style={{ fontSize: '14px' }}>{label}</span>
              <Toggle value={config[key] !== false} onChange={v => updateField(key, v)} />
            </div>
          ))}
        </div>
      </div>

      <div style={styles.card}>
        <div style={styles.cardTitle}><Eye size={18} /> Parametres d'Inference</div>
        <div style={styles.grid(2)}>
          <div>
            <label style={styles.label}>Seuil de confiance ({(config.confidence_threshold || 0.25).toFixed(2)})</label>
            <input type="range" min="0.05" max="0.95" step="0.05"
              value={config.confidence_threshold || 0.25}
              onChange={e => updateField('confidence_threshold', parseFloat(e.target.value))}
              style={{ width: '100%' }} />
          </div>
          <div>
            <label style={styles.label}>Seuil IoU ({(config.iou_threshold || 0.45).toFixed(2)})</label>
            <input type="range" min="0.1" max="0.9" step="0.05"
              value={config.iou_threshold || 0.45}
              onChange={e => updateField('iou_threshold', parseFloat(e.target.value))}
              style={{ width: '100%' }} />
          </div>
        </div>
      </div>

      <button style={styles.btnPrimary} onClick={onSave}>
        <CheckCircle size={16} /> Sauvegarder la configuration
      </button>
    </div>
  );
}

// ============================================================
// GENERATION PAGE
// ============================================================

function GeneratePage() {
  const [params, setParams] = useState({ num_images: 100, seed: 42, use_v3: true });
  const [jobs, setJobs] = useState({});
  const [polling, setPolling] = useState(false);

  const startGeneration = async () => {
    try {
      const res = await fetch(`${API_URL}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      });
      const data = await res.json();
      setPolling(true);
    } catch (e) {
      alert('Erreur: ' + e.message);
    }
  };

  useEffect(() => {
    if (!polling) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/status`);
        const data = await res.json();
        setJobs(data.jobs || {});
        const running = Object.values(data.jobs || {}).some(j => j.status === 'running');
        if (!running) setPolling(false);
      } catch (e) {}
    }, 2000);
    return () => clearInterval(interval);
  }, [polling]);

  return (
    <div>
      <div style={styles.card}>
        <div style={styles.cardTitle}><Database size={18} /> Generation de Dataset</div>
        <div style={styles.grid(3)}>
          <div>
            <label style={styles.label}>Nombre d'images</label>
            <input style={styles.input} type="number" value={params.num_images}
              onChange={e => setParams(p => ({ ...p, num_images: parseInt(e.target.value) }))} />
          </div>
          <div>
            <label style={styles.label}>Seed</label>
            <input style={styles.input} type="number" value={params.seed}
              onChange={e => setParams(p => ({ ...p, seed: parseInt(e.target.value) }))} />
          </div>
          <div>
            <label style={styles.label}>Version</label>
            <select style={styles.input} value={params.use_v3 ? 'v3' : 'v2'}
              onChange={e => setParams(p => ({ ...p, use_v3: e.target.value === 'v3' }))}>
              <option value="v3">V3 (PBR + Distracteurs + Artefacts)</option>
              <option value="v2">V2 (Original)</option>
            </select>
          </div>
        </div>
        <button style={styles.btnPrimary} onClick={startGeneration}>
          <Play size={16} /> Lancer la generation
        </button>
      </div>

      {Object.entries(jobs).filter(([_, j]) => j.type === 'generate').map(([id, job]) => (
        <div key={id} style={styles.card}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <div style={styles.cardTitle}>
              <Activity size={18} /> Job: {id}
            </div>
            <span style={styles.badge(
              job.status === 'completed' ? '#10b981' :
              job.status === 'failed' ? '#ef4444' : '#f59e0b'
            )}>
              {job.status === 'completed' ? <CheckCircle size={14} /> :
               job.status === 'failed' ? <XCircle size={14} /> :
               <Clock size={14} />}
              {job.status}
            </span>
          </div>
          <div style={styles.progress}>
            <div style={styles.progressBar(job.progress || 0,
              job.status === 'completed' ? '#10b981' :
              job.status === 'failed' ? '#ef4444' : '#3b82f6'
            )} />
          </div>
          <div style={{ marginTop: '8px', fontSize: '13px', color: '#94a3b8' }}>
            {(job.progress || 0).toFixed(1)}% - Demarre: {job.started_at || '—'}
            {job.completed_at && ` | Termine: ${job.completed_at}`}
          </div>
        </div>
      ))}
    </div>
  );
}

// ============================================================
// TRAINING PAGE
// ============================================================

function TrainingPage() {
  const [params, setParams] = useState({ model: 'yolov8n.pt', epochs: 50, batch: 16, imgsz: 640, name: 'battery_sorting' });
  const [metrics, setMetrics] = useState(null);
  const [jobs, setJobs] = useState({});
  const [trainingResults, setTrainingResults] = useState(null);
  const [polling, setPolling] = useState(false);
  const [selectedResultImg, setSelectedResultImg] = useState(null);

  const startTraining = async () => {
    try {
      const res = await fetch(`${API_URL}/train`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      });
      await res.json();
      setPolling(true);
    } catch (e) {
      alert('Erreur: ' + e.message);
    }
  };

  const loadMetrics = async () => {
    try {
      const res = await fetch(`${API_URL}/metrics`);
      const data = await res.json();
      setMetrics(data);
    } catch (e) {}
  };

  const loadTrainingResults = async () => {
    try {
      const res = await fetch(`${API_URL}/training/results`);
      const data = await res.json();
      setTrainingResults(data);
    } catch (e) {}
  };

  useEffect(() => { loadMetrics(); loadTrainingResults(); }, []);

  useEffect(() => {
    if (!polling) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/status`);
        const data = await res.json();
        setJobs(data.jobs || {});
        const running = Object.values(data.jobs || {}).some(j => j.type === 'train' && j.status === 'running');
        if (!running) {
          setPolling(false);
          loadMetrics();
          loadTrainingResults();
        }
      } catch (e) {}
    }, 3000);
    return () => clearInterval(interval);
  }, [polling]);

  // Fixed: use clean header names matching actual CSV
  const chartData = metrics?.history
    ? (metrics.history['epoch'] || []).map((epoch, i) => ({
        epoch: i + 1,
        train_loss: metrics.history['train/box_loss']?.[i],
        val_loss: metrics.history['val/box_loss']?.[i],
        mAP50: metrics.history['metrics/mAP50(B)']?.[i],
        mAP50_95: metrics.history['metrics/mAP50-95(B)']?.[i],
        precision: metrics.history['metrics/precision(B)']?.[i],
        recall: metrics.history['metrics/recall(B)']?.[i],
      }))
    : [];

  const fm = trainingResults?.final_metrics || {};

  // Group result images by category
  const resultImageGroups = trainingResults?.available_images ? {
    'Matrice de confusion': trainingResults.available_images.filter(f => f.includes('confusion')),
    'Courbes de performance': trainingResults.available_images.filter(f => f.includes('curve') || f === 'results.png'),
    'Exemples de detection': trainingResults.available_images.filter(f => f.includes('val_batch') && f.includes('pred')),
    'Labels': trainingResults.available_images.filter(f => (f.includes('val_batch') && f.includes('label')) || f === 'labels.jpg'),
    'Train batches': trainingResults.available_images.filter(f => f.includes('train_batch')),
  } : {};

  return (
    <div className="fade-in">
      <div style={styles.card}>
        <div style={styles.cardTitle}><Cpu size={18} /> Entrainement YOLO</div>
        <div style={styles.grid(4)}>
          <div>
            <label style={styles.label}>Modele</label>
            <select style={styles.input} value={params.model}
              onChange={e => setParams(p => ({ ...p, model: e.target.value }))}>
              <option value="yolov8n.pt">YOLOv8n (Nano)</option>
              <option value="yolov8s.pt">YOLOv8s (Small)</option>
              <option value="yolov8m.pt">YOLOv8m (Medium)</option>
              <option value="yolov8l.pt">YOLOv8l (Large)</option>
            </select>
          </div>
          <div>
            <label style={styles.label}>Epochs</label>
            <input style={styles.input} type="number" value={params.epochs}
              onChange={e => setParams(p => ({ ...p, epochs: parseInt(e.target.value) }))} />
          </div>
          <div>
            <label style={styles.label}>Batch size</label>
            <input style={styles.input} type="number" value={params.batch}
              onChange={e => setParams(p => ({ ...p, batch: parseInt(e.target.value) }))} />
          </div>
          <div>
            <label style={styles.label}>Image size</label>
            <input style={styles.input} type="number" value={params.imgsz}
              onChange={e => setParams(p => ({ ...p, imgsz: parseInt(e.target.value) }))} />
          </div>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button style={styles.btnPrimary} onClick={startTraining}>
            <Play size={16} /> Lancer l'entrainement
          </button>
          <button style={styles.btnSecondary} onClick={() => { loadMetrics(); loadTrainingResults(); }}>
            <RefreshCw size={16} /> Rafraichir les metriques
          </button>
        </div>
      </div>

      {/* Training jobs */}
      {Object.entries(jobs).filter(([_, j]) => j.type === 'train').map(([id, job]) => (
        <div key={id} style={styles.card}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span>Job: {id}</span>
            <span style={styles.badge(
              job.status === 'completed' ? '#10b981' :
              job.status === 'failed' ? '#ef4444' : '#f59e0b'
            )}>{job.status}</span>
          </div>
          <div style={styles.progress}>
            <div style={styles.progressBar(job.progress || 0)} />
          </div>
          <div style={{ marginTop: '8px', fontSize: '13px', color: '#94a3b8' }}>
            {(job.progress || 0).toFixed(1)}% complete
          </div>
        </div>
      ))}

      {/* Final Metrics Summary */}
      {trainingResults && !trainingResults.message && (
        <div style={styles.card}>
          <div style={styles.cardTitle}><CheckCircle size={18} /> Resultats — {trainingResults.run_name}</div>
          <div style={styles.grid(4)}>
            <div style={{...styles.stat, borderLeft: '3px solid #10b981'}}>
              <div style={styles.statLabel}>mAP@50</div>
              <div style={{...styles.statValue, color: '#10b981'}}>{((fm['metrics/mAP50(B)'] || 0) * 100).toFixed(1)}%</div>
            </div>
            <div style={{...styles.stat, borderLeft: '3px solid #8b5cf6'}}>
              <div style={styles.statLabel}>mAP@50-95</div>
              <div style={{...styles.statValue, color: '#8b5cf6'}}>{((fm['metrics/mAP50-95(B)'] || 0) * 100).toFixed(1)}%</div>
            </div>
            <div style={{...styles.stat, borderLeft: '3px solid #f59e0b'}}>
              <div style={styles.statLabel}>Precision</div>
              <div style={{...styles.statValue, color: '#f59e0b'}}>{((fm['metrics/precision(B)'] || 0) * 100).toFixed(1)}%</div>
            </div>
            <div style={{...styles.stat, borderLeft: '3px solid #ec4899'}}>
              <div style={styles.statLabel}>Recall</div>
              <div style={{...styles.statValue, color: '#ec4899'}}>{((fm['metrics/recall(B)'] || 0) * 100).toFixed(1)}%</div>
            </div>
          </div>
          <div style={{ fontSize: '13px', color: '#94a3b8', marginTop: '8px' }}>
            {fm.epoch ? `${Math.round(fm.epoch)} epochs` : ''} — Poids: {trainingResults.weights?.join(', ') || 'N/A'}
          </div>
        </div>
      )}

      {/* Metrics Charts */}
      {chartData && chartData.length > 0 && (
        <>
          <div style={styles.grid(2)}>
            <div style={styles.card}>
              <div style={styles.cardTitle}><TrendingUp size={18} /> Loss</div>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3e" />
                  <XAxis dataKey="epoch" stroke="#94a3b8" fontSize={12} />
                  <YAxis stroke="#94a3b8" fontSize={12} />
                  <Tooltip contentStyle={{ background: '#1a1b2e', border: '1px solid #2a2d3e', borderRadius: '8px' }} />
                  <Legend />
                  <Line type="monotone" dataKey="train_loss" stroke="#3b82f6" name="Train Loss" dot={false} />
                  <Line type="monotone" dataKey="val_loss" stroke="#ef4444" name="Val Loss" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div style={styles.card}>
              <div style={styles.cardTitle}><TrendingUp size={18} /> mAP</div>
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3e" />
                  <XAxis dataKey="epoch" stroke="#94a3b8" fontSize={12} />
                  <YAxis stroke="#94a3b8" fontSize={12} domain={[0, 1]} />
                  <Tooltip contentStyle={{ background: '#1a1b2e', border: '1px solid #2a2d3e', borderRadius: '8px' }} />
                  <Legend />
                  <Area type="monotone" dataKey="mAP50" stroke="#10b981" fill="#10b98120" name="mAP@50" />
                  <Area type="monotone" dataKey="mAP50_95" stroke="#8b5cf6" fill="#8b5cf620" name="mAP@50-95" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div style={styles.card}>
            <div style={styles.cardTitle}><TrendingUp size={18} /> Precision & Recall</div>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3e" />
                <XAxis dataKey="epoch" stroke="#94a3b8" fontSize={12} />
                <YAxis stroke="#94a3b8" fontSize={12} domain={[0, 1]} />
                <Tooltip contentStyle={{ background: '#1a1b2e', border: '1px solid #2a2d3e', borderRadius: '8px' }} />
                <Legend />
                <Line type="monotone" dataKey="precision" stroke="#f59e0b" name="Precision" dot={false} />
                <Line type="monotone" dataKey="recall" stroke="#ec4899" name="Recall" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      {/* Training Result Images */}
      {trainingResults && !trainingResults.message && Object.entries(resultImageGroups).map(([group, imgs]) => (
        imgs.length > 0 && (
          <div key={group} style={styles.card}>
            <div style={styles.cardTitle}><Eye size={18} /> {group}</div>
            <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(imgs.length, 3)}, 1fr)`, gap: '12px' }}>
              {imgs.map(img => (
                <div key={img} onClick={() => setSelectedResultImg(img)} style={{ cursor: 'pointer', transition: 'transform 0.2s' }}
                  onMouseEnter={e => e.currentTarget.style.transform = 'scale(1.02)'}
                  onMouseLeave={e => e.currentTarget.style.transform = 'scale(1)'}>
                  <img src={`${API_URL}/training/images/${img}`} alt={img}
                    style={{ width: '100%', borderRadius: '8px', border: '1px solid #2a2d3e' }} />
                  <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px', textAlign: 'center' }}>{img}</div>
                </div>
              ))}
            </div>
          </div>
        )
      ))}

      {/* Fullscreen image modal */}
      {selectedResultImg && (
        <div onClick={() => setSelectedResultImg(null)} style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.9)', display: 'flex', alignItems: 'center',
          justifyContent: 'center', zIndex: 1000, padding: '20px', cursor: 'pointer',
        }}>
          <img src={`${API_URL}/training/images/${selectedResultImg}`} alt={selectedResultImg}
            onClick={e => e.stopPropagation()}
            style={{ maxWidth: '90vw', maxHeight: '90vh', borderRadius: '12px', cursor: 'default' }}
            className="fade-in" />
        </div>
      )}
    </div>
  );
}

// ============================================================
// INFERENCE PAGE
// ============================================================

function InferencePage() {
  const [predictions, setPredictions] = useState([]);
  const [inferenceTime, setInferenceTime] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [imageSize, setImageSize] = useState(null);
  const [webcamActive, setWebcamActive] = useState(false);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const animFrameRef = useRef(null);
  const fileInputRef = useRef(null);

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setImagePreview(URL.createObjectURL(file));

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API_URL}/predict`, { method: 'POST', body: formData });
      const data = await res.json();
      setPredictions(data.predictions || []);
      setInferenceTime(data.inference_time_ms);
      setImageSize(data.image_size);
    } catch (e) {
      alert('Erreur: ' + e.message);
    }
  };

  const startWebcam = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        setWebcamActive(true);
      }
    } catch (e) {
      alert('Erreur webcam: ' + e.message);
    }
  };

  const stopWebcam = () => {
    if (videoRef.current?.srcObject) {
      videoRef.current.srcObject.getTracks().forEach(t => t.stop());
      videoRef.current.srcObject = null;
    }
    setWebcamActive(false);
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
    }
  };

  const captureAndPredict = useCallback(async () => {
    if (!videoRef.current || !canvasRef.current || !webcamActive) return;

    const canvas = canvasRef.current;
    const video = videoRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);

    const imageData = canvas.toDataURL('image/jpeg', 0.8);

    try {
      const res = await fetch(`${API_URL}/predict/webcam`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: imageData }),
      });
      const data = await res.json();
      setPredictions(data.predictions || []);
      setInferenceTime(data.inference_time_ms);

      // Dessiner les bboxes
      const ctx = canvas.getContext('2d');
      data.predictions?.forEach((pred, i) => {
        const { x1, y1, x2, y2 } = pred.bbox;
        ctx.strokeStyle = COLORS[pred.class_id % COLORS.length];
        ctx.lineWidth = 2;
        ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
        ctx.fillStyle = COLORS[pred.class_id % COLORS.length];
        ctx.font = '14px Inter';
        ctx.fillText(`${pred.class_name} ${(pred.confidence * 100).toFixed(0)}%`, x1, y1 - 4);
      });
    } catch (e) {}

    if (webcamActive) {
      animFrameRef.current = setTimeout(() => captureAndPredict(), 200);  // 5 FPS
    }
  }, [webcamActive]);

  useEffect(() => {
    if (webcamActive) {
      setTimeout(() => captureAndPredict(), 500);
    }
    return () => {
      if (animFrameRef.current) clearTimeout(animFrameRef.current);
    };
  }, [webcamActive, captureAndPredict]);

  return (
    <div className="fade-in">
      <div style={styles.grid(2)}>
        {/* Upload */}
        <div style={styles.card}>
          <div style={styles.cardTitle}><Upload size={18} /> Upload d'image</div>
          <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileUpload}
            style={{ display: 'none' }} />
          <div
            onClick={() => fileInputRef.current?.click()}
            onDragOver={e => { e.preventDefault(); e.currentTarget.style.borderColor = '#3b82f6'; e.currentTarget.style.background = '#1a1b2e'; }}
            onDragLeave={e => { e.preventDefault(); e.currentTarget.style.borderColor = '#2a2d3e'; e.currentTarget.style.background = '#0f1117'; }}
            onDrop={e => {
              e.preventDefault();
              e.currentTarget.style.borderColor = '#2a2d3e';
              e.currentTarget.style.background = '#0f1117';
              const file = e.dataTransfer.files[0];
              if (file && file.type.startsWith('image/')) {
                handleFileUpload({ target: { files: [file] } });
              }
            }}
            style={{
              border: '2px dashed #2a2d3e', borderRadius: '12px', padding: '40px',
              textAlign: 'center', cursor: 'pointer', marginBottom: '16px',
              background: '#0f1117', transition: 'all 0.2s',
            }}>
            <Upload size={32} color="#94a3b8" />
            <p style={{ color: '#94a3b8', marginTop: '8px' }}>Cliquez ou glissez-deposez une image</p>
          </div>
          {imagePreview && (
            <div style={{ position: 'relative' }}>
              <img src={imagePreview} alt="preview" style={{ width: '100%', borderRadius: '8px' }} />
              {/* Overlay bboxes */}
              {predictions.map((pred, i) => {
                if (!imageSize) return null;
                const { x1, y1, x2, y2 } = pred.bbox;
                const scaleX = 1;  // Simplified - would need actual display ratio
                return (
                  <div key={i} style={{
                    position: 'absolute', left: `${x1/imageSize.width*100}%`, top: `${y1/imageSize.height*100}%`,
                    width: `${(x2-x1)/imageSize.width*100}%`, height: `${(y2-y1)/imageSize.height*100}%`,
                    border: `2px solid ${COLORS[pred.class_id % COLORS.length]}`,
                    borderRadius: '4px',
                  }}>
                    <span style={{
                      position: 'absolute', top: '-20px', left: '0',
                      background: COLORS[pred.class_id % COLORS.length],
                      color: '#fff', fontSize: '11px', padding: '1px 6px', borderRadius: '4px',
                      whiteSpace: 'nowrap',
                    }}>
                      {pred.class_name} {(pred.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Webcam */}
        <div style={styles.card}>
          <div style={styles.cardTitle}><Camera size={18} /> Detection Webcam</div>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
            <button style={webcamActive ? styles.btnSecondary : styles.btnPrimary}
              onClick={webcamActive ? stopWebcam : startWebcam}>
              {webcamActive ? <><XCircle size={16} /> Arreter</> : <><Camera size={16} /> Demarrer</>}
            </button>
          </div>
          <video ref={videoRef} autoPlay playsInline muted
            style={{ width: '100%', borderRadius: '8px', display: webcamActive ? 'block' : 'none' }} />
          <canvas ref={canvasRef}
            style={{ width: '100%', borderRadius: '8px', display: webcamActive ? 'block' : 'none', marginTop: '8px' }} />
          {!webcamActive && (
            <div style={{ textAlign: 'center', padding: '60px 0', color: '#94a3b8' }}>
              <Camera size={48} />
              <p>Cliquez sur Demarrer pour activer la webcam</p>
            </div>
          )}
        </div>
      </div>

      {/* Results */}
      {predictions.length > 0 && (
        <div style={styles.card}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={styles.cardTitle}><Zap size={18} /> Resultats</div>
            {inferenceTime && (
              <span style={styles.badge('#10b981')}>
                <Clock size={14} /> {inferenceTime.toFixed(1)}ms
              </span>
            )}
          </div>
          <div style={styles.grid(Math.min(predictions.length, 4))}>
            {predictions.map((pred, i) => (
              <div key={i} style={{
                ...styles.stat,
                borderLeft: `3px solid ${COLORS[pred.class_id % COLORS.length]}`,
              }}>
                <div style={styles.statLabel}>{pred.class_name}</div>
                <div style={{ ...styles.statValue, color: COLORS[pred.class_id % COLORS.length] }}>
                  {(pred.confidence * 100).toFixed(1)}%
                </div>
                <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px' }}>
                  ({pred.bbox.x1.toFixed(0)}, {pred.bbox.y1.toFixed(0)}) - ({pred.bbox.x2.toFixed(0)}, {pred.bbox.y2.toFixed(0)})
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================
// DATASET PAGE
// ============================================================

function DatasetPage() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [images, setImages] = useState([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalImages, setTotalImages] = useState(0);
  const [selectedImage, setSelectedImage] = useState(null);
  const [annotations, setAnnotations] = useState(null);
  const [galleryLoading, setGalleryLoading] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_URL}/dataset/stats`);
        const data = await res.json();
        setStats(data);
      } catch (e) {}
      setLoading(false);
    })();
  }, []);

  const loadImages = useCallback(async (p) => {
    setGalleryLoading(true);
    try {
      const res = await fetch(`${API_URL}/dataset/images/list?page=${p}&per_page=12`);
      const data = await res.json();
      setImages(data.images || []);
      setTotalPages(data.total_pages || 1);
      setTotalImages(data.total || 0);
    } catch (e) {}
    setGalleryLoading(false);
  }, []);

  useEffect(() => { loadImages(page); }, [page, loadImages]);

  const openImageDetail = async (img) => {
    setSelectedImage(img);
    try {
      const res = await fetch(`${API_URL}/dataset/images/${img.filename}/annotations`);
      const data = await res.json();
      setAnnotations(data);
    } catch (e) { setAnnotations(null); }
  };

  if (loading) return <div style={styles.card}><RefreshCw size={16} className="spin" /> Chargement...</div>;

  const classData = stats?.per_class_count
    ? Object.entries(stats.per_class_count).map(([name, count]) => ({ name, count }))
    : [];

  return (
    <div className="fade-in">
      {/* Stats row */}
      <div style={styles.grid(4)}>
        <div style={styles.stat}>
          <div style={styles.statLabel}>Images</div>
          <div style={{ ...styles.statValue, color: '#3b82f6' }}>{stats?.num_images || stats?.images || totalImages || 0}</div>
        </div>
        <div style={styles.stat}>
          <div style={styles.statLabel}>Annotations</div>
          <div style={{ ...styles.statValue, color: '#8b5cf6' }}>{stats?.num_annotations || 0}</div>
        </div>
        <div style={styles.stat}>
          <div style={styles.statLabel}>Moteur</div>
          <div style={{ ...styles.statValue, fontSize: '18px', color: '#10b981' }}>{stats?.render_engine || 'N/A'}</div>
        </div>
        <div style={styles.stat}>
          <div style={styles.statLabel}>Temps total</div>
          <div style={{ ...styles.statValue, color: '#f59e0b' }}>
            {stats?.total_time_seconds ? `${(stats.total_time_seconds / 60).toFixed(1)}min` : 'N/A'}
          </div>
        </div>
      </div>

      {stats?.version === 'v3' && (
        <div style={styles.card}>
          <div style={styles.cardTitle}><Zap size={18} /> Features V3</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {(stats.features || []).map(f => (
              <span key={f} style={styles.badge('#3b82f6')}>{f.replace(/_/g, ' ')}</span>
            ))}
          </div>
        </div>
      )}

      {/* Image Gallery */}
      <div style={styles.card}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div style={styles.cardTitle}><Camera size={18} /> Galerie d'images ({totalImages})</div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <button style={styles.btnSecondary} disabled={page <= 1}
              onClick={() => setPage(p => Math.max(1, p - 1))}>← Precedent</button>
            <span style={{ fontSize: '13px', color: '#94a3b8' }}>{page} / {totalPages}</span>
            <button style={styles.btnSecondary} disabled={page >= totalPages}
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}>Suivant →</button>
          </div>
        </div>

        {galleryLoading ? (
          <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>
            <RefreshCw size={24} className="spin" />
            <p style={{ marginTop: '8px' }}>Chargement des images...</p>
          </div>
        ) : images.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>
            <Database size={32} />
            <p style={{ marginTop: '8px' }}>Aucune image dans le dataset. Lancez une generation.</p>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
            {images.map(img => (
              <div key={img.filename}
                onClick={() => openImageDetail(img)}
                style={{
                  background: '#0f1117', borderRadius: '10px', overflow: 'hidden',
                  border: '1px solid #2a2d3e', cursor: 'pointer',
                  transition: 'all 0.2s', position: 'relative',
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = '#3b82f6'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = '#2a2d3e'; e.currentTarget.style.transform = 'translateY(0)'; }}
              >
                <img
                  src={`${API_URL}/dataset/images/${img.filename}`}
                  alt={img.filename}
                  loading="lazy"
                  style={{ width: '100%', height: '160px', objectFit: 'cover', display: 'block' }}
                />
                <div style={{ padding: '8px 10px' }}>
                  <div style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>{img.filename}</div>
                  <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                    <span style={styles.badge('#8b5cf6')}>{img.annotation_count} obj</span>
                    {img.classes.slice(0, 3).map(c => (
                      <span key={c} style={styles.badge('#3b82f6')}>{c}</span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Charts */}
      {classData.length > 0 && (
        <div style={styles.grid(2)}>
          <div style={styles.card}>
            <div style={styles.cardTitle}><BarChart3 size={18} /> Distribution par classe</div>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={classData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3e" />
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} />
                <YAxis stroke="#94a3b8" fontSize={12} />
                <Tooltip contentStyle={{ background: '#1a1b2e', border: '1px solid #2a2d3e', borderRadius: '8px' }} />
                <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                  {classData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div style={styles.card}>
            <div style={styles.cardTitle}><Box size={18} /> Repartition</div>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie data={classData} dataKey="count" nameKey="name" cx="50%" cy="50%"
                  innerRadius={60} outerRadius={100} paddingAngle={3}>
                  {classData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: '#1a1b2e', border: '1px solid #2a2d3e', borderRadius: '8px' }} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Image Detail Modal */}
      {selectedImage && (
        <div onClick={() => { setSelectedImage(null); setAnnotations(null); }} style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.85)', display: 'flex', alignItems: 'center',
          justifyContent: 'center', zIndex: 1000, padding: '20px',
        }}>
          <div onClick={e => e.stopPropagation()} style={{
            background: '#1a1b2e', borderRadius: '16px', border: '1px solid #2a2d3e',
            maxWidth: '900px', width: '100%', maxHeight: '90vh', overflow: 'auto', padding: '24px',
          }} className="fade-in">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={styles.cardTitle}><Eye size={18} /> {selectedImage.filename}</div>
              <button onClick={() => { setSelectedImage(null); setAnnotations(null); }}
                style={{ ...styles.btnSecondary, padding: '6px 12px' }}>
                <XCircle size={16} /> Fermer
              </button>
            </div>
            <div style={{ position: 'relative', marginBottom: '16px' }}>
              <img src={`${API_URL}/dataset/images/${selectedImage.filename}`}
                alt={selectedImage.filename}
                style={{ width: '100%', borderRadius: '8px', display: 'block' }} />
              {annotations?.annotations?.map((ann, i) => {
                const imgSize = annotations.image_size;
                return (
                  <div key={i} style={{
                    position: 'absolute',
                    left: `${ann.bbox.x1 / imgSize.width * 100}%`,
                    top: `${ann.bbox.y1 / imgSize.height * 100}%`,
                    width: `${(ann.bbox.x2 - ann.bbox.x1) / imgSize.width * 100}%`,
                    height: `${(ann.bbox.y2 - ann.bbox.y1) / imgSize.height * 100}%`,
                    border: `2px solid ${COLORS[ann.class_id % COLORS.length]}`,
                    borderRadius: '3px',
                  }}>
                    <span style={{
                      position: 'absolute', top: '-18px', left: '0',
                      background: COLORS[ann.class_id % COLORS.length],
                      color: '#fff', fontSize: '10px', padding: '1px 5px', borderRadius: '3px',
                      whiteSpace: 'nowrap',
                    }}>{ann.class_name}</span>
                  </div>
                );
              })}
            </div>
            {annotations && (
              <div style={{ fontSize: '13px', color: '#94a3b8' }}>
                {annotations.annotations.length} annotations — Taille: {annotations.image_size.width}x{annotations.image_size.height}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================
// APP PRINCIPALE
// ============================================================

function App() {
  const [page, setPage] = useState('dataset');
  const [config, setConfig] = useState({});
  const [apiStatus, setApiStatus] = useState('checking');

  const checkApi = useCallback(async () => {
    setApiStatus('checking');
    try {
      const res = await fetch(`${API_URL}/`);
      await res.json();
      setApiStatus('connected');
      const configRes = await fetch(`${API_URL}/config`);
      const configData = await configRes.json();
      setConfig(configData);
    } catch (e) {
      setApiStatus('disconnected');
    }
  }, []);

  useEffect(() => { checkApi(); }, [checkApi]);

  const saveConfig = async () => {
    try {
      await fetch(`${API_URL}/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      alert('Configuration sauvegardee !');
    } catch (e) {
      alert('Erreur: ' + e.message);
    }
  };

  const pages = [
    { id: 'dataset', label: 'Dataset', icon: Database },
    { id: 'generate', label: 'Generation', icon: Play },
    { id: 'training', label: 'Training', icon: TrendingUp },
    { id: 'inference', label: 'Inference', icon: Eye },
    { id: 'config', label: 'Config', icon: Settings },
  ];

  return (
    <div style={styles.app}>
      <header style={styles.header}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Zap size={24} color="#3b82f6" />
          <span style={styles.headerTitle}>Battery Sorting AI</span>
          <span style={{ fontSize: '12px', color: '#94a3b8', marginLeft: '8px' }}>v3.0</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <nav style={styles.nav}>
            {pages.map(p => (
              <button key={p.id} style={styles.navBtn(page === p.id)} onClick={() => setPage(p.id)}>
                <p.icon size={14} /> {p.label}
              </button>
            ))}
          </nav>
          <span
            onClick={apiStatus !== 'connected' ? checkApi : undefined}
            style={{
              ...styles.badge(
                apiStatus === 'connected' ? '#10b981' :
                apiStatus === 'checking' ? '#f59e0b' : '#ef4444'
              ),
              cursor: apiStatus !== 'connected' ? 'pointer' : 'default',
            }}
          >
            {apiStatus === 'connected' ? <CheckCircle size={12} /> :
             apiStatus === 'checking' ? <RefreshCw size={12} className="spin" /> :
             <AlertTriangle size={12} />}
            {apiStatus === 'connected' ? 'API connectee' :
             apiStatus === 'checking' ? 'Connexion...' :
             'API deconnectee — Cliquez pour reconnecter'}
          </span>
        </div>
      </header>

      <main style={styles.main}>
        {page === 'config' && <ConfigPage config={config} setConfig={setConfig} onSave={saveConfig} />}
        {page === 'generate' && <GeneratePage />}
        {page === 'training' && <TrainingPage />}
        {page === 'inference' && <InferencePage />}
        {page === 'dataset' && <DatasetPage />}
      </main>
    </div>
  );
}

export default App;

