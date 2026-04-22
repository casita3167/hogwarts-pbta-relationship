import React, { useState, useEffect, useRef } from 'react';
import { initializeApp } from 'firebase/app';
import { 
  getFirestore, collection, doc, onSnapshot, setDoc, updateDoc, deleteDoc 
} from 'firebase/firestore';
import { 
  getAuth, onAuthStateChanged, signInAnonymously 
} from 'firebase/auth';
import { 
  Users, UserPlus, Link as LinkIcon, Hexagon, Download, Settings2, 
  Trash2, Upload, Move, ZoomIn, ZoomOut, Maximize, X, Check, ArrowRightLeft, ArrowRight
} from 'lucide-react';
import * as d3 from 'd3';

// --- Firebase 配置 (直接寫入物件，解決白屏問題) ---
const firebaseConfig = {
  apiKey: "AIzaSyDV06_5tTecR4q9EZUQ32IBy91KsFxsCHA",
  authDomain: "hogwarts-pbta-relationsh-31ba9.firebaseapp.com",
  projectId: "hogwarts-pbta-relationsh-31ba9",
  storageBucket: "hogwarts-pbta-relationsh-31ba9.firebasestorage.app",
  messagingSenderId: "361459597273",
  appId: "1:361459597273:web:66c7174720052f826323c8"
};

// 初始化 Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);
const appId = 'org-chart-gen-006'; // 固定 ID 方便開發

const DEFAULT_AVATAR = `data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iI2UyZThmMCI+PHBhdGggZD0iTTEyIDJDMiAyIDIgMTEgMiAxMVMxMiAyMiAxMiAyMnMxMC0xMSAxMC0xMVMyMiAyIDEyIDJ6bTAgNWEzIDMgMCAxIDEgMCA2IDMgMyAwIDAgMSAwLTZ6bTcgMTFIMTV2LTFjMC0xLjY2LTEuMzQtMy0zLTNzLTMgMS4zNC0zIDN2MUg1di0xYzAtMi43NiAyLjI0LTUgNS01aDRjMi43NiAwIDUgMi4yNCA1IDV2MXoiLz48L3N2Zz4=`;

const App = () => {
  const [user, setUser] = useState(null);
  const [nodes, setNodes] = useState([]);
  const [links, setLinks] = useState([]);
  const [groups, setGroups] = useState([]);
  const [viewMode, setViewMode] = useState('force'); 
  const [selectedNode, setSelectedNode] = useState(null);
  const [isSidebarOpen, setSidebarOpen] = useState(true);
  const [isAvatarModalOpen, setAvatarModalOpen] = useState(false);
  const [tempAvatar, setTempAvatar] = useState(null);
  const [libLoaded, setLibLoaded] = useState(false);
  
  const [editingName, setEditingName] = useState("");
  const [editingGroupNames, setEditingGroupNames] = useState({});
  const [editingLinkLabels, setEditingLinkLabels] = useState({});

  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const simulationRef = useRef(null);
  const gRef = useRef(null); 

  useEffect(() => {
    const script = document.createElement('script');
    script.src = "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js";
    script.async = true;
    script.onload = () => setLibLoaded(true);
    document.body.appendChild(script);
    return () => { if (document.body.contains(script)) document.body.removeChild(script); };
  }, []);

  useEffect(() => {
    signInAnonymously(auth).catch(err => console.error(err));
    const unsub = onAuthStateChanged(auth, setUser);
    return () => unsub();
  }, []);

  useEffect(() => {
    if (!user) return;
    const unsubNodes = onSnapshot(collection(db, 'artifacts', appId, 'public', 'data', 'nodes'), (s) => setNodes(s.docs.map(d => ({id: d.id, ...d.data()}))));
    const unsubLinks = onSnapshot(collection(db, 'artifacts', appId, 'public', 'data', 'links'), (s) => setLinks(s.docs.map(d => ({id: d.id, ...d.data()}))));
    const unsubGroups = onSnapshot(collection(db, 'artifacts', appId, 'public', 'data', 'groups'), (s) => setGroups(s.docs.map(d => ({id: d.id, ...d.data()}))));
    return () => { unsubNodes(); unsubLinks(); unsubGroups(); };
  }, [user]);

  useEffect(() => {
    setEditingName(selectedNode?.name || "");
  }, [selectedNode?.id]);

  const getLinkId = (ref) => (typeof ref === 'object' && ref !== null) ? ref.id : ref;

  // --- D3 渲染核心 ---
  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return;
    
    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;
    const svg = d3.select(svgRef.current);

    if (!gRef.current) {
      const g = svg.append("g");
      gRef.current = g;
      const zoom = d3.zoom().scaleExtent([0.1, 5]).on("zoom", (e) => g.attr("transform", e.transform));
      svg.call(zoom);

      const defs = g.append("defs");
      const mk = (id, rx) => defs.append("marker").attr("id", id).attr("viewBox", "0 -5 10 10").attr("refX", rx).attr("refY", 0).attr("orient", "auto").attr("markerWidth", 6).attr("markerHeight", 6).append("path").attr("d", "M0,-5L10,0L0,5").attr("fill", "#94a3b8");
      mk("arrow-end", 40); mk("arrow-start", -30);
      
      g.append("g").attr("class", "groups-layer");
      g.append("g").attr("class", "links-layer");
      g.append("g").attr("class", "labels-layer");
      g.append("g").attr("class", "nodes-layer");
    }

    const g = gRef.current;
    const validLinks = links.filter(l => nodes.some(n => n.id === getLinkId(l.source)) && nodes.some(n => n.id === getLinkId(l.target)));

    if (!simulationRef.current) {
      simulationRef.current = d3.forceSimulation(nodes)
        .velocityDecay(0.4) 
        .force("link", d3.forceLink(validLinks).id(d => d.id).distance(160))
        .force("charge", d3.forceManyBody().strength(-200))
        .force("x", d3.forceX(width / 2).strength(0.08))
        .force("y", d3.forceY(height / 2).strength(0.08))
        .force("collision", d3.forceCollide().radius(75));
    } else {
      simulationRef.current.nodes(nodes);
      simulationRef.current.force("link").links(validLinks);
    }

    const nodeData = g.select(".nodes-layer").selectAll(".node-group").data(nodes, d => d.id);
    const nodeEnter = nodeData.enter().append("g").attr("class", "node-group").attr("cursor", "pointer")
      .on("click", (e, d) => { e.stopPropagation(); setSelectedNode(d); })
      .call(d3.drag().on("start", dragstarted).on("drag", dragged).on("end", dragended));

    nodeEnter.append("circle").attr("class", "node-circle").attr("r", 32).attr("fill", "#fff").attr("stroke", "#e2e8f0").attr("stroke-width", 2);
    nodeEnter.append("clipPath").attr("id", d => `clip-${d.id}`).append("circle").attr("r", 30);
    nodeEnter.append("image").attr("x", -30).attr("y", -30).attr("width", 60).attr("height", 60).attr("clip-path", d => `url(#clip-${d.id})`);
    nodeEnter.append("text").attr("dy", 50).attr("text-anchor", "middle").attr("font-weight", "600").attr("font-size", "12px").attr("fill", "#1e293b");

    const nodeUpdate = nodeEnter.merge(nodeData);
    nodeUpdate.select("image").attr("xlink:href", d => d.avatar || DEFAULT_AVATAR);
    nodeUpdate.select("text").text(d => d.name);
    nodeData.exit().remove();

    const linkData = g.select(".links-layer").selectAll(".link-path").data(validLinks, d => d.id);
    const linkEnter = linkData.enter().append("path").attr("class", "link-path").attr("fill", "none").attr("stroke", "#cbd5e1").attr("stroke-width", 2);
    const linkUpdate = linkEnter.merge(linkData);
    linkUpdate.attr("marker-end", d => (d.type === 'unidirectional' || d.type === 'bidirectional') ? "url(#arrow-end)" : "")
              .attr("marker-start", d => d.type === 'bidirectional' ? "url(#arrow-start)" : "");
    linkData.exit().remove();

    const labelData = g.select(".labels-layer").selectAll(".link-label").data(validLinks, d => d.id);
    const labelEnter = labelData.enter().append("text").attr("class", "link-label").attr("font-size", "11px").attr("font-weight", "bold").attr("fill", "#64748b").attr("text-anchor", "middle").style("paint-order", "stroke").style("stroke", "#ffffff").style("stroke-width", "3px");
    const labelUpdate = labelEnter.merge(labelData);
    labelUpdate.text(d => d.label || "");
    labelData.exit().remove();

    simulationRef.current.on("tick", ticked);

    function ticked() {
      const lGroups = {};
      validLinks.forEach(l => { const p = [getLinkId(l.source), getLinkId(l.target)].sort().join("-"); if (!lGroups[p]) lGroups[p] = []; lGroups[p].push(l); });
      linkUpdate.attr("d", d => {
        const s = nodes.find(n => n.id === getLinkId(d.source)), t = nodes.find(n => n.id === getLinkId(d.target));
        if (!s || !t) return "";
        const group = lGroups[[s.id, t.id].sort().join("-")], idx = group.indexOf(d), count = group.length;
        if (count === 1) return `M${s.x},${s.y}L${t.x},${t.y}`;
        const dx = t.x - s.x, dy = t.y - s.y, dist = Math.sqrt(dx * dx + dy * dy);
        const nx = -dy / dist, ny = dx / dist, bend = (idx - (count - 1) / 2) * 35;
        return `M${s.x},${s.y} Q${(s.x + t.x)/2 + nx * bend},${(s.y + t.y)/2 + ny * bend} ${t.x},${t.y}`;
      });
      labelUpdate.attr("transform", d => {
        const s = nodes.find(n => n.id === getLinkId(d.source)), t = nodes.find(n => n.id === getLinkId(d.target));
        if (!s || !t) return "";
        const group = lGroups[[s.id, t.id].sort().join("-")], idx = group.indexOf(d), count = group.length;
        const midX = (s.x + t.x) / 2, midY = (s.y + t.y) / 2;
        if (count === 1) return `translate(${midX},${midY - 12})`;
        const dx = t.x - s.x, dy = t.y - s.y, dist = Math.sqrt(dx * dx + dy * dy);
        const nx = -dy / dist, ny = dx / dist, bend = (idx - (count - 1) / 2) * 35;
        return `translate(${midX + nx * (bend * 0.55)},${midY + ny * (bend * 0.55)})`;
      });
      nodeUpdate.attr("transform", d => `translate(${d.x},${d.y})`);
      const hulls = g.select(".groups-layer").selectAll(".group-hull").data(groups, d => d.id);
      hulls.enter().append("path").attr("class", "group-hull").lower().attr("fill-opacity", 0.1).attr("stroke-width", 2).attr("stroke-dasharray", "8 4").merge(hulls).attr("fill", d => d.color || "#ccc").attr("stroke", d => d.color || "#999").attr("d", gData => {
        const gNodes = nodes.filter(n => gData.memberIds?.includes(n.id));
        if (gNodes.length === 0) return "";
        const pts = gNodes.map(n => [n.x, n.y]), pad = 55;
        if (pts.length === 1) return `M ${pts[0][0]-pad},${pts[0][1]} a ${pad},${pad} 0 1,0 ${pad*2},0 a ${pad},${pad} 0 1,0 -${pad*2},0`;
        const hp = []; pts.forEach(p => [0, 1.57, 3.14, 4.71].forEach(a => hp.push([p[0]+Math.cos(a)*pad, p[1]+Math.sin(a)*pad])));
        const hull = d3.polygonHull(hp); return hull ? d3.line().curve(d3.curveBasisClosed)(hull) : "";
      });
      hulls.exit().remove();
    }

    function dragstarted(e) {
      if (viewMode === 'flat') return;
      e.subject.fx = e.subject.x;
      e.subject.fy = e.subject.y;
    }

    function dragged(e) {
      if (viewMode === 'flat') {
        e.subject.x = e.x; e.subject.y = e.y;
        ticked();
      } else {
        if (!e.active) simulationRef.current.alphaTarget(0.01).restart();
        e.subject.fx = e.x;
        e.subject.fy = e.y;
      }
    }

    function dragended(e) { 
      if (!e.active) simulationRef.current.alphaTarget(0); 
      e.subject.fx = null; e.subject.fy = null; 
      updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'nodes', e.subject.id), { x: e.x, y: e.y });
    }
    
    if (viewMode === 'flat') simulationRef.current.stop(); else simulationRef.current.alpha(0.05).restart();
  }, [nodes, links, groups, viewMode]);

  // --- 視覺聚焦效果：鄰居 + 同組成員 ---
  useEffect(() => {
    if (!gRef.current) return;
    const g = gRef.current;
    const focusIds = new Set();
    if (selectedNode) {
      focusIds.add(selectedNode.id);
      
      // 鄰居
      links.forEach(l => {
        const s = getLinkId(l.source), t = getLinkId(l.target);
        if (s === selectedNode.id) focusIds.add(t); if (t === selectedNode.id) focusIds.add(s);
      });
      
      // 同組成員
      groups.forEach(group => { 
        if (group.memberIds?.includes(selectedNode.id)) {
          group.memberIds.forEach(id => focusIds.add(id));
        }
      });
    }

    const t = d3.transition().duration(250);
    g.selectAll(".link-path").transition(t).style("opacity", d => {
      const s = getLinkId(d.source), t = getLinkId(d.target);
      return !selectedNode || (s === selectedNode.id || t === selectedNode.id) ? 1 : 0.05;
    });
    g.selectAll(".link-label").transition(t).style("opacity", d => {
      const s = getLinkId(d.source), t = getLinkId(d.target);
      return !selectedNode || (s === selectedNode.id || t === selectedNode.id) ? 1 : 0.05;
    });
    g.selectAll(".node-group").transition(t).style("opacity", d => (!selectedNode || focusIds.has(d.id)) ? 1 : 0.1);
    g.selectAll(".node-circle").attr("stroke", d => selectedNode?.id === d.id ? "#6366f1" : "#e2e8f0").attr("stroke-width", d => selectedNode?.id === d.id ? 4 : 2);
    g.selectAll(".group-hull").transition(t).style("opacity", d => (!selectedNode || d.memberIds?.includes(selectedNode.id)) ? 1 : 0.35);
  }, [selectedNode?.id, links, groups]);

  const handleDownload = async () => {
    if (!libLoaded || !containerRef.current || !window.html2canvas) return;
    try {
      const canvas = await window.html2canvas(containerRef.current, { backgroundColor: '#ffffff', useCORS: true, allowTaint: true, scale: 2 });
      const link = document.createElement('a');
      link.download = `組織關係圖_${Date.now()}.png`; link.href = canvas.toDataURL('image/png'); link.click();
    } catch (err) { console.error("下載失敗:", err); }
  };

  const handleSaveAvatar = async () => {
    if (selectedNode && tempAvatar) {
      await updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'nodes', selectedNode.id), { avatar: tempAvatar });
      setAvatarModalOpen(false); setTempAvatar(null);
    }
  };

  return (
    <div className="flex h-screen w-full bg-slate-50 text-slate-900 overflow-hidden font-sans custom-font-stack">
      <aside className={`bg-white border-r border-slate-200 transition-all duration-300 flex flex-col z-50 shadow-2xl shrink-0 ${isSidebarOpen ? 'w-80' : 'w-0 overflow-hidden'}`}>
        <div className="p-4 bg-indigo-600 text-white flex justify-between items-center shadow-md shrink-0">
          <h1 className="font-bold flex items-center gap-2">👥 組織生成器</h1>
          <button onClick={() => setSidebarOpen(false)} className="hover:bg-indigo-700 w-8 h-8 rounded transition-colors flex items-center justify-center text-lg">✖</button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-6 text-slate-700">
          <section className="bg-amber-50 p-4 rounded-2xl border border-amber-200 flex gap-3 shadow-sm">
             <div className="text-amber-600 shrink-0 text-xl">💡</div>
             <div className="text-[13px] text-amber-800 leading-relaxed font-medium">
                <strong>使用說明：</strong><br/>建議先用「手動佈局」擺放角色，再用「力導向圖」看效果。
             </div>
          </section>
          <section className="space-y-2">
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest px-1">地圖管理</h2>
            <div className="grid grid-cols-2 gap-2">
              <button onClick={() => setDoc(doc(db, 'artifacts', appId, 'public', 'data', 'nodes', crypto.randomUUID()), { name: "新成員", avatar: "", x: 400, y: 300 })} className="flex items-center justify-center gap-2 bg-indigo-50 text-indigo-700 py-2.5 rounded-xl hover:bg-indigo-100 text-sm font-bold transition-all">👤+ 新角色</button>
              <button onClick={() => setDoc(doc(db, 'artifacts', appId, 'public', 'data', 'groups', crypto.randomUUID()), { name: "新分組", color: "#6366f1", memberIds: [] })} className="flex items-center justify-center gap-2 bg-slate-100 text-slate-700 py-2.5 rounded-xl hover:bg-slate-200 text-sm font-bold transition-all">💠 新分組</button>
            </div>
          </section>
          {selectedNode ? (
            <section className="bg-slate-50 p-4 rounded-2xl border border-slate-200 space-y-4 shadow-inner">
              <div className="flex justify-between items-center border-b pb-2">
                <h2 className="font-bold text-slate-700 truncate mr-2">編輯：{String(selectedNode.name || "成員")}</h2>
                <button onClick={() => { deleteDoc(doc(db, 'artifacts', appId, 'public', 'data', 'nodes', selectedNode.id)); setSelectedNode(null); }} className="text-red-400 hover:text-red-600 p-1 rounded hover:bg-red-50 text-lg">🗑</button>
              </div>
              <div className="space-y-4">
                <label className="block space-y-1">
                  <span className="text-xs font-bold text-slate-400">角色名稱</span>
                  <input type="text" value={editingName || ""} onChange={(e) => setEditingName(e.target.value)} onBlur={() => updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'nodes', selectedNode.id), { name: editingName })} className="w-full rounded-lg border-slate-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-200 transition-all bg-white shadow-sm" />
                </label>
                <div className="flex items-center gap-3">
                   <div className="w-14 h-14 rounded-full overflow-hidden border-2 border-white shadow-sm shrink-0 bg-white"><img src={selectedNode.avatar || DEFAULT_AVATAR} className="w-full h-full object-cover" /></div>
                   <label className="cursor-pointer bg-white border border-slate-200 px-3 py-1.5 rounded-lg text-xs font-bold hover:bg-slate-50 shadow-sm transition-all text-slate-600">更換頭像 <input type="file" className="hidden" accept="image/*" onChange={(e) => { const file = e.target.files[0]; if (file) { const reader = new FileReader(); reader.onload = (ev) => { setTempAvatar(ev.target.result); setAvatarModalOpen(true); }; reader.readAsDataURL(file); } }} /></label>
                </div>
                <div className="space-y-2"><span className="text-xs font-bold text-slate-400 uppercase tracking-widest">建立關係</span>
                  <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto pr-1">
                    {nodes.filter(n => n.id !== selectedNode.id).map(n => (
                      <button key={n.id} onClick={() => setDoc(doc(db, 'artifacts', appId, 'public', 'data', 'links', crypto.randomUUID()), { source: selectedNode.id, target: n.id, type: 'unidirectional', label: '新關係' })} className="text-[10px] bg-white border border-indigo-100 text-indigo-600 px-2 py-1 rounded-full hover:bg-indigo-50 transition-colors shadow-sm">+ {String(n.name || "成員")}</button>
                    ))}
                  </div>
                </div>
                <div className="space-y-2"><span className="text-xs font-bold text-slate-400 uppercase tracking-widest">目前關係</span>
                  <div className="space-y-1.5">
                    {links.filter(l => getLinkId(l.source) === selectedNode.id || getLinkId(l.target) === selectedNode.id).map(l => {
                      const curLabel = editingLinkLabels[l.id] ?? l.label ?? "";
                      return (
                        <div key={l.id} className="flex items-center gap-1 bg-white p-1.5 rounded-lg border border-slate-200 shadow-sm">
                          <input type="text" value={String(curLabel)} onChange={(e) => setEditingLinkLabels(p => ({...p, [l.id]: e.target.value}))} onBlur={() => updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'links', l.id), { label: curLabel })} className="text-[10px] font-bold border-0 p-0 flex-1 outline-none ml-1 bg-transparent" />
                          <button onClick={() => updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'links', l.id), { type: l.type === 'unidirectional' ? 'bidirectional' : 'unidirectional' })} className="p-1 text-slate-400 hover:text-indigo-600 transition-colors">🔄</button>
                          <button onClick={() => deleteDoc(doc(db, 'artifacts', appId, 'public', 'data', 'links', l.id))} className="p-1 text-red-300 hover:text-red-500 transition-colors">🗑</button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </section>
          ) : (
            <div className="text-center py-16 opacity-30 flex flex-col items-center"><div className="text-4xl mb-2">👥</div><p className="text-xs font-bold font-sans">點選角色開始編輯</p></div>
          )}
          <section className="space-y-3 pb-8"><h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest px-1">角色分組</h2>
            {groups.map(g => {
              const curGName = editingGroupNames[g.id] ?? g.name ?? "";
              return (
                <div key={g.id} className="flex items-center gap-2 bg-white p-2.5 rounded-xl border border-slate-200 group hover:border-indigo-200 transition-all shadow-sm">
                  <input type="color" value={g.color ?? "#6366f1"} onChange={(e) => updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'groups', g.id), { color: e.target.value })} className="w-5 h-5 rounded cursor-pointer border-0 p-0 overflow-hidden" />
                  <input type="text" value={String(curGName)} onChange={(e) => setEditingGroupNames(p => ({...p, [g.id]: e.target.value}))} onBlur={() => updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'groups', g.id), { name: curGName })} className="text-xs font-bold flex-1 border-0 p-0 outline-none bg-transparent" />
                  <input type="checkbox" checked={!!(selectedNode && g.memberIds?.includes(selectedNode.id))} onChange={() => selectedNode && handleToggleGroup(g.id, selectedNode.id)} className="w-3.5 h-3.5 rounded text-indigo-600 cursor-pointer" />
                  <button onClick={() => deleteDoc(doc(db, 'artifacts', appId, 'public', 'data', 'groups', g.id))} className="opacity-0 group-hover:opacity-100 text-red-300 hover:text-red-500 text-sm">🗑</button>
                </div>
              );
            })}
          </section>
        </div>
      </aside>

      <main className="flex-1 relative bg-white">
        <div className="absolute top-6 left-6 z-40 flex gap-3 items-center">
          {!isSidebarOpen && (
            <button onClick={() => setSidebarOpen(true)} className="bg-white w-12 h-12 rounded-2xl shadow-xl border border-slate-100 text-indigo-600 hover:scale-105 active:scale-95 transition-all flex items-center justify-center shrink-0 text-xl">⚙️</button>
          )}
          <div className="flex bg-white rounded-2xl shadow-xl border border-slate-100 p-1.5 font-bold text-[13px] ring-1 ring-slate-100">
            <button onClick={() => setViewMode('force')} className={`px-6 py-2.5 rounded-xl transition-all ${viewMode === 'force' ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-400 hover:bg-slate-50'}`}>力導向圖</button>
            <button onClick={() => setViewMode('flat')} className={`px-6 py-2.5 rounded-xl transition-all ${viewMode === 'flat' ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-400 hover:bg-slate-50'}`}>手動佈局</button>
          </div>
        </div>
        <div className="absolute top-6 right-6 z-40"><button disabled={!libLoaded} onClick={handleDownload} className="flex items-center gap-2 bg-slate-900 text-white px-7 py-3.5 rounded-2xl shadow-2xl hover:bg-black font-bold text-sm transition-all active:scale-95 disabled:opacity-50 shadow-black/20">💾 匯出圖檔</button></div>
        <div ref={containerRef} className="w-full h-full"><svg ref={svgRef} className="w-full h-full" onClick={() => setSelectedNode(null)} /></div>
      </main>

      {isAvatarModalOpen && (
        <div className="fixed inset-0 bg-slate-900/70 backdrop-blur-md z-[100] flex items-center justify-center p-6 animate-in fade-in duration-300">
          <div className="bg-white rounded-[40px] shadow-2xl max-w-sm w-full p-10 animate-in zoom-in duration-200 border border-white/20">
            <div className="text-center mb-8"><h3 className="text-2xl font-black text-slate-800 tracking-tight">頭像預覽</h3></div>
            <div className="relative aspect-square w-full rounded-full overflow-hidden border-[12px] border-indigo-50 bg-slate-50 mb-10 mx-auto max-w-[240px] shadow-inner ring-1 ring-slate-200">{tempAvatar && <img src={tempAvatar} className="w-full h-full object-cover" alt="preview" />}</div>
            <div className="flex gap-4">
              <button onClick={() => { setAvatarModalOpen(false); setTempAvatar(null); }} className="flex-1 py-4 rounded-[20px] border-2 border-slate-100 font-bold text-slate-500 transition-colors hover:bg-slate-50">取消</button>
              <button onClick={handleSaveAvatar} className="flex-1 py-4 rounded-[20px] bg-indigo-600 text-white font-bold shadow-xl shadow-indigo-100 hover:bg-indigo-700 transition-all flex items-center justify-center gap-2">✅ 儲存</button>
            </div>
          </div>
        </div>
      )}
      <style dangerouslySetInnerHTML={{ __html: `
        .custom-font-stack { font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif, "Microsoft JhengHei"; }
        svg { background-color: #ffffff; outline: none; }
        .group-hull { transition: opacity 0.3s ease; pointer-events: none; }
        text { pointer-events: none; user-select: none; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-thumb { background: #e2e8f0; border-radius: 10px; }
        .node-group, .link-path, .link-label { transition: opacity 0.3s ease; }
      `}} />
    </div>
  );
};

export default App;