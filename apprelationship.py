import React, { useState, useEffect, useRef } from 'react';
import { initializeApp } from 'firebase/app';
import { 
  getFirestore, collection, doc, onSnapshot, setDoc, updateDoc, deleteDoc
} from 'firebase/firestore';
import { 
  getAuth, onAuthStateChanged, signInWithCustomToken, signInAnonymously 
} from 'firebase/auth';
import { 
  Users, UserPlus, Link as LinkIcon, Hexagon, Download, Settings2, 
  Trash2, Upload, Move, ZoomIn, ZoomOut, Maximize, X, Check, ArrowRightLeft, ArrowRight
} from 'lucide-react';
import * as d3 from 'd3';

// --- Firebase 配置 ---
const firebaseConfig = JSON.parse(__firebase_config);
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);
const appId = typeof __app_id !== 'undefined' ? __app_id : 'org-chart-gen-003';

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
  
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const simulationRef = useRef(null);

  // 動態載入 html2canvas 以支援圖檔匯出
  useEffect(() => {
    const script = document.createElement('script');
    script.src = "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js";
    script.async = true;
    script.onload = () => setLibLoaded(true);
    document.body.appendChild(script);
    return () => { if (document.body.contains(script)) document.body.removeChild(script); };
  }, []);

  // Firebase 認證 (Rule 3)
  useEffect(() => {
    const initAuth = async () => {
      try {
        if (typeof __initial_auth_token !== 'undefined' && __initial_auth_token) {
          await signInWithCustomToken(auth, __initial_auth_token);
        } else {
          await signInAnonymously(auth);
        }
      } catch (err) { console.error("Auth error:", err); }
    };
    initAuth();
    const unsubscribeAuth = onAuthStateChanged(auth, setUser);
    return () => unsubscribeAuth();
  }, []);

  // Firestore 資料監聽 (Rule 1)
  useEffect(() => {
    if (!user) return;
    const nodesRef = collection(db, 'artifacts', appId, 'public', 'data', 'nodes');
    const linksRef = collection(db, 'artifacts', appId, 'public', 'data', 'links');
    const groupsRef = collection(db, 'artifacts', appId, 'public', 'data', 'groups');

    const unsubNodes = onSnapshot(nodesRef, (snap) => setNodes(snap.docs.map(d => ({ id: d.id, ...d.data() }))));
    const unsubLinks = onSnapshot(linksRef, (snap) => setLinks(snap.docs.map(d => ({ id: d.id, ...d.data() }))));
    const unsubGroups = onSnapshot(groupsRef, (snap) => setGroups(snap.docs.map(d => ({ id: d.id, ...d.data() }))));

    return () => { unsubNodes(); unsubLinks(); unsubGroups(); };
  }, [user]);

  // --- D3 渲染邏輯 ---
  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return;

    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const g = svg.append("g");

    const zoom = d3.zoom()
      .scaleExtent([0.1, 5])
      .on("zoom", (e) => g.attr("transform", e.transform));
    svg.call(zoom);

    // 定義箭頭樣式
    const defs = svg.append("defs");
    defs.append("marker")
      .attr("id", "arrow-end")
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 42).attr("refY", 0)
      .attr("orient", "auto").attr("markerWidth", 6).attr("markerHeight", 6)
      .append("path").attr("d", "M0,-5L10,0L0,5").attr("fill", "#94a3b8");
    defs.append("marker")
      .attr("id", "arrow-start")
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", -32).attr("refY", 0)
      .attr("orient", "auto").attr("markerWidth", 6).attr("markerHeight", 6)
      .append("path").attr("d", "M10,-5L0,0L10,5").attr("fill", "#94a3b8");

    const groupLayer = g.append("g").attr("class", "groups-layer");

    // 計算連線組以處理重疊 (弧線)
    const linkGroups = {};
    links.forEach(l => {
      const sourceId = typeof l.source === 'object' ? l.source.id : l.source;
      const targetId = typeof l.target === 'object' ? l.target.id : l.target;
      const pair = [sourceId, targetId].sort().join("-");
      if (!linkGroups[pair]) linkGroups[pair] = [];
      linkGroups[pair].push(l);
    });

    const linkElements = g.append("g")
      .selectAll("path")
      .data(links)
      .enter().append("path")
      .attr("fill", "none")
      .attr("stroke", "#cbd5e1")
      .attr("stroke-width", 2)
      .attr("marker-end", d => (d.type === 'unidirectional' || d.type === 'bidirectional') ? "url(#arrow-end)" : "")
      .attr("marker-start", d => d.type === 'bidirectional' ? "url(#arrow-start)" : "");

    const linkLabels = g.append("g")
      .selectAll("text")
      .data(links)
      .enter().append("text")
      .attr("font-size", "10px")
      .attr("fill", "#64748b")
      .attr("text-anchor", "middle")
      .text(d => d.label || "");

    const nodeElements = g.append("g")
      .selectAll("g")
      .data(nodes)
      .enter().append("g")
      .attr("cursor", "pointer")
      .on("click", (e, d) => setSelectedNode(d))
      .call(d3.drag()
        .on("start", dragstarted)
        .on("drag", dragged)
        .on("end", dragended));

    nodeElements.append("circle")
      .attr("r", 32)
      .attr("fill", "#fff")
      .attr("stroke", d => selectedNode?.id === d.id ? "#6366f1" : "#e2e8f0")
      .attr("stroke-width", d => selectedNode?.id === d.id ? 4 : 2);

    nodeElements.append("clipPath")
      .attr("id", d => `clip-${d.id}`)
      .append("circle").attr("r", 30);

    nodeElements.append("image")
      .attr("xlink:href", d => d.avatar || `https://api.dicebear.com/7.x/bottts-neutral/svg?seed=${d.name}`)
      .attr("x", -30).attr("y", -30).attr("width", 60).attr("height", 60)
      .attr("clip-path", d => `url(#clip-${d.id})`);

    nodeElements.append("text")
      .attr("dy", 50).attr("text-anchor", "middle").attr("font-weight", "600").attr("font-size", "12px").attr("fill", "#1e293b")
      .text(d => d.name);

    const simulation = d3.forceSimulation(nodes)
      .force("link", d3.forceLink(links).id(d => d.id).distance(220))
      .force("charge", d3.forceManyBody().strength(-800))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide().radius(80));

    simulationRef.current = simulation;

    if (viewMode === 'flat') {
      simulation.stop();
      ticked();
    } else {
      simulation.on("tick", ticked);
    }

    function ticked() {
      linkElements.attr("d", d => {
        const source = d.source;
        const target = d.target;
        const sourceId = source.id || source;
        const targetId = target.id || target;
        const pair = [sourceId, targetId].sort().join("-");
        const group = linkGroups[pair];
        const index = group.indexOf(d);
        const count = group.length;
        
        const dx = target.x - source.x;
        const dy = target.y - source.y;
        const dr = (count > 1) ? Math.sqrt(dx * dx + dy * dy) * (1 + index * 0.3) : 0;
        const sweep = sourceId < targetId ? 1 : 0;

        if (dr === 0) return `M${source.x},${source.y}L${target.x},${target.y}`;
        return `M${source.x},${source.y}A${dr},${dr} 0 0,${sweep} ${target.x},${target.y}`;
      });

      linkLabels.attr("transform", d => {
        const source = d.source;
        const target = d.target;
        const x = (source.x + target.x) / 2;
        const y = (source.y + target.y) / 2;
        return `translate(${x},${y-15})`;
      });

      nodeElements.attr("transform", d => `translate(${d.x},${d.y})`);

      groupLayer.selectAll("path").remove();
      groups.forEach(group => {
        const groupNodes = nodes.filter(n => group.memberIds?.includes(n.id));
        if (groupNodes.length === 0) return;
        const pts = groupNodes.map(n => [n.x, n.y]);
        let pathStr = "";
        if (pts.length === 1) {
          pathStr = `M ${pts[0][0]-65},${pts[0][1]} a 65,65 0 1,0 130,0 a 65,65 0 1,0 -130,0`;
        } else if (pts.length === 2) {
          const [x1, y1] = pts[0], [x2, y2] = pts[1];
          const dx = x2 - x1, dy = y2 - y1, len = Math.sqrt(dx*dx + dy*dy);
          const off = 65, nx = dy/len*off, ny = -dx/len*off;
          pathStr = `M ${x1+nx},${y1+ny} L ${x2+nx},${y2+ny} A ${off},${off} 0 0 1 ${x2-nx},${y2-ny} L ${x1-nx},${y1-ny} A ${off},${off} 0 0 1 ${x1+nx},${y1+ny}`;
        } else {
          const hull = d3.polygonHull(pts);
          if (hull) pathStr = d3.line().curve(d3.curveBasisClosed)(hull);
        }
        groupLayer.append("path").attr("d", pathStr).attr("fill", group.color).attr("fill-opacity", 0.08).attr("stroke", group.color).attr("stroke-width", 2).attr("stroke-dasharray", "6 4").lower();
      });
    }

    function dragstarted(event) {
      if (viewMode === 'flat') return;
      if (!event.active) simulation.alphaTarget(0.3).restart();
      event.subject.fx = event.subject.x;
      event.subject.fy = event.subject.y;
    }

    function dragged(event) {
      event.subject.x = event.x;
      event.subject.y = event.y;
      if (viewMode === 'flat') {
        ticked(); // 手動觸發重繪解決脫離問題
      } else {
        event.subject.fx = event.x;
        event.subject.fy = event.y;
      }
    }

    function dragended(event) {
      if (viewMode === 'flat') {
        updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'nodes', event.subject.id), { x: event.subject.x, y: event.subject.y });
      } else {
        if (!event.active) simulation.alphaTarget(0);
        event.subject.fx = null; event.subject.fy = null;
        updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'nodes', event.subject.id), { x: event.subject.x, y: event.subject.y });
      }
    }
  }, [nodes, links, groups, viewMode, selectedNode]);

  // --- 處理函式 ---

  const handleAddNode = async () => {
    const id = crypto.randomUUID();
    await setDoc(doc(db, 'artifacts', appId, 'public', 'data', 'nodes', id), { name: "新成員", avatar: "", x: 400, y: 300 });
  };

  const handleDeleteNode = async (id) => {
    await deleteDoc(doc(db, 'artifacts', appId, 'public', 'data', 'nodes', id));
    links.forEach(async l => {
      const sId = l.source.id || l.source;
      const tId = l.target.id || l.target;
      if (sId === id || tId === id) {
        await deleteDoc(doc(db, 'artifacts', appId, 'public', 'data', 'links', l.id));
      }
    });
    setSelectedNode(null);
  };

  const handleAddLink = async (targetId) => {
    if (!selectedNode || selectedNode.id === targetId) return;
    const id = crypto.randomUUID();
    await setDoc(doc(db, 'artifacts', appId, 'public', 'data', 'links', id), {
      source: selectedNode.id,
      target: targetId,
      type: 'unidirectional',
      label: '新關係'
    });
  };

  const handleUpdateLink = async (linkId, data) => {
    await updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'links', linkId), data);
  };

  const handleAddGroup = async () => {
    const id = crypto.randomUUID();
    await setDoc(doc(db, 'artifacts', appId, 'public', 'data', 'groups', id), {
      name: "新秘密結社", color: "#" + Math.floor(Math.random()*16777215).toString(16), memberIds: []
    });
  };

  const handleToggleGroup = async (groupId, nodeId) => {
    const group = groups.find(g => g.id === groupId);
    let members = [...(group.memberIds || [])];
    members = members.includes(nodeId) ? members.filter(id => id !== nodeId) : [...members, nodeId];
    await updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'groups', groupId), { memberIds: members });
  };

  const handleDownload = async () => {
    if (!libLoaded || !containerRef.current) return;
    // 使用 html2canvas 擷取畫布區域
    const canvas = await window.html2canvas(containerRef.current, {
      backgroundColor: '#ffffff',
      useCORS: true,
      scale: 2
    });
    const link = document.createElement('a');
    link.download = `組織關係圖_${Date.now()}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
  };

  const handleAvatarFile = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (ev) => {
        setTempAvatar(ev.target.result);
        setAvatarModalOpen(true);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSaveAvatar = async () => {
    if (selectedNode && tempAvatar) {
      await updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'nodes', selectedNode.id), {
        avatar: tempAvatar
      });
      setAvatarModalOpen(false);
      setTempAvatar(null);
    }
  };

  return (
    <div className="flex h-screen w-full bg-slate-50 text-slate-900 overflow-hidden font-sans">
      {/* 側邊編輯欄 */}
      <aside className={`bg-white border-r border-slate-200 transition-all duration-300 flex flex-col z-30 shadow-2xl ${isSidebarOpen ? 'w-80' : 'w-0 overflow-hidden'}`}>
        <div className="p-4 bg-indigo-600 text-white flex justify-between items-center">
          <h1 className="font-bold flex items-center gap-2"><Users size={20} /> 組織生成器</h1>
          <button onClick={() => setSidebarOpen(false)} className="hover:bg-indigo-700 p-1 rounded"><X size={18} /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          <section className="space-y-2">
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest">新增元件</h2>
            <div className="grid grid-cols-2 gap-2">
              <button onClick={handleAddNode} className="flex items-center justify-center gap-2 bg-indigo-50 text-indigo-700 py-2.5 rounded-xl hover:bg-indigo-100 text-sm font-bold transition-all"><UserPlus size={16} /> 新角色</button>
              <button onClick={handleAddGroup} className="flex items-center justify-center gap-2 bg-slate-100 text-slate-700 py-2.5 rounded-xl hover:bg-slate-200 text-sm font-bold transition-all"><Hexagon size={16} /> 新結社</button>
            </div>
          </section>

          {selectedNode ? (
            <section className="bg-slate-50 p-4 rounded-2xl border border-slate-200 space-y-4 animate-in slide-in-from-right duration-200">
              <div className="flex justify-between items-center">
                <h2 className="font-bold text-slate-700 text-lg">角色設定</h2>
                <button onClick={() => handleDeleteNode(selectedNode.id)} className="text-red-400 hover:text-red-600 transition-colors"><Trash2 size={18} /></button>
              </div>
              
              <div className="space-y-4">
                <input 
                  type="text" 
                  value={selectedNode.name}
                  onChange={(e) => updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'nodes', selectedNode.id), { name: e.target.value })}
                  className="w-full rounded-xl border-slate-200 bg-white px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-100 outline-none shadow-sm"
                />
                
                <div className="flex items-center gap-4">
                  <img src={selectedNode.avatar || `https://api.dicebear.com/7.x/bottts-neutral/svg?seed=${selectedNode.name}`} className="w-16 h-16 rounded-full border-4 border-white shadow-md" alt="avatar" />
                  <label className="cursor-pointer bg-white border border-slate-200 px-4 py-2 rounded-xl text-xs font-bold hover:bg-slate-50 shadow-sm transition-all">
                    更換頭像
                    <input type="file" className="hidden" accept="image/*" onChange={handleAvatarFile} />
                  </label>
                </div>

                <div className="space-y-2">
                  <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">建立新關係</span>
                  <div className="flex flex-wrap gap-2">
                    {nodes.filter(n => n.id !== selectedNode.id).map(n => (
                      <button key={n.id} onClick={() => handleAddLink(n.id)} className="text-[10px] bg-white border border-indigo-100 text-indigo-600 px-2.5 py-1.5 rounded-full hover:bg-indigo-50 font-bold transition-all shadow-sm">
                        + {n.name}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">關係管理 (雙向/單向)</span>
                  <div className="space-y-2 max-h-40 overflow-y-auto">
                    {links.filter(l => {
                      const sId = l.source.id || l.source;
                      const tId = l.target.id || l.target;
                      return sId === selectedNode.id || tId === selectedNode.id;
                    }).map(l => {
                      const sId = l.source.id || l.source;
                      const tId = l.target.id || l.target;
                      const targetId = sId === selectedNode.id ? tId : sId;
                      const targetNode = nodes.find(n => n.id === targetId);
                      return (
                        <div key={l.id} className="flex items-center justify-between bg-white p-2 rounded-lg border border-slate-100 shadow-sm">
                          <div className="flex flex-col">
                            <span className="text-[10px] text-slate-400">對應：{targetNode?.name}</span>
                            <input 
                              type="text" value={l.label} 
                              onChange={(e) => handleUpdateLink(l.id, { label: e.target.value })}
                              className="text-[11px] font-bold border-0 p-0 focus:ring-0 w-20"
                            />
                          </div>
                          <div className="flex gap-1">
                            <button 
                              onClick={() => handleUpdateLink(l.id, { type: l.type === 'unidirectional' ? 'bidirectional' : 'unidirectional' })}
                              className={`p-1.5 rounded-md transition-all ${l.type === 'bidirectional' ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-400'}`}
                              title={l.type === 'bidirectional' ? '切換為單向' : '切換為雙向'}
                            >
                              <ArrowRightLeft size={12} />
                            </button>
                            <button onClick={() => deleteDoc(doc(db, 'artifacts', appId, 'public', 'data', 'links', l.id))} className="p-1.5 bg-red-50 text-red-400 rounded-md hover:bg-red-100"><Trash2 size={12} /></button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </section>
          ) : (
            <div className="text-center py-20 border-2 border-dashed border-slate-100 rounded-[32px]">
              <Move className="mx-auto mb-4 text-slate-200" size={48} />
              <p className="text-sm text-slate-300 font-medium">點選角色進行編輯</p>
            </div>
          )}

          <section className="space-y-3">
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest">秘密結社</h2>
            {groups.map(g => (
              <div key={g.id} className="p-4 bg-white border border-slate-200 rounded-2xl flex items-center justify-between shadow-sm group hover:border-indigo-200 transition-all">
                <div className="flex items-center gap-3">
                  <input type="color" value={g.color} onChange={(e) => updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'groups', g.id), { color: e.target.value })} className="w-8 h-8 rounded-lg border-0 p-0 cursor-pointer shadow-sm" />
                  <input type="text" value={g.name} onChange={(e) => updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'groups', g.id), { name: e.target.value })} className="text-sm font-bold border-0 p-0 focus:ring-0 w-32 bg-transparent text-slate-700" />
                </div>
                <button onClick={() => deleteDoc(doc(db, 'artifacts', appId, 'public', 'data', 'groups', g.id))} className="text-slate-200 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all"><Trash2 size={16} /></button>
              </div>
            ))}
          </section>
        </div>
      </aside>

      {/* 主畫布區域 */}
      <main className="flex-1 relative flex flex-col bg-slate-50">
        <div className="absolute top-6 left-6 z-20 flex gap-3">
          {!isSidebarOpen && (
            <button onClick={() => setSidebarOpen(true)} className="bg-white p-3 rounded-2xl shadow-xl border border-slate-200 text-indigo-600 hover:scale-110 transition-all"><Settings2 size={24} /></button>
          )}
          <div className="flex bg-white rounded-2xl shadow-xl border border-slate-200 p-1.5 ring-1 ring-black/5">
            <button onClick={() => setViewMode('force')} className={`px-6 py-2.5 rounded-xl text-sm font-black transition-all ${viewMode === 'force' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-100' : 'text-slate-400 hover:bg-slate-50'}`}>物理引力</button>
            <button onClick={() => setViewMode('flat')} className={`px-6 py-2.5 rounded-xl text-sm font-black transition-all ${viewMode === 'flat' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-100' : 'text-slate-400 hover:bg-slate-50'}`}>自由定位</button>
          </div>
        </div>

        <div className="absolute top-6 right-6 z-20">
           <button disabled={!libLoaded} onClick={handleDownload} className="flex items-center gap-2 bg-slate-900 text-white px-7 py-3.5 rounded-2xl shadow-2xl hover:bg-black font-black text-sm transition-all active:scale-95 disabled:opacity-50"><Download size={20} /> 匯出圖檔</button>
        </div>

        <div ref={containerRef} className="flex-1 bg-white relative overflow-hidden">
          <svg ref={svgRef} className="w-full h-full" onClick={(e) => e.target.tagName === 'svg' && setSelectedNode(null)} />
        </div>
      </main>

      {/* 頭像預覽 Modal */}
      {isAvatarModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-md z-50 flex items-center justify-center p-6 animate-in fade-in duration-300">
          <div className="bg-white rounded-[40px] shadow-2xl max-w-sm w-full p-10 animate-in zoom-in duration-200 border border-white/20">
            <div className="text-center mb-8"><h3 className="text-2xl font-black text-slate-800 tracking-tight">頭像裁切預覽</h3></div>
            <div className="relative aspect-square w-full rounded-full overflow-hidden border-[12px] border-indigo-50 bg-slate-50 mb-10 mx-auto max-w-[240px] shadow-inner ring-1 ring-slate-200">
              {tempAvatar && <img src={tempAvatar} className="w-full h-full object-cover" alt="preview" />}
            </div>
            <div className="flex gap-4">
              <button onClick={() => setAvatarModalOpen(false)} className="flex-1 py-4 rounded-[20px] border-2 border-slate-100 font-bold text-slate-400 hover:bg-slate-50">取消</button>
              <button onClick={handleSaveAvatar} className="flex-1 py-4 rounded-[20px] bg-indigo-600 text-white font-bold shadow-xl shadow-indigo-100 hover:bg-indigo-700 transition-all flex items-center justify-center gap-2"><Check size={20} /> 儲存</button>
            </div>
          </div>
        </div>
      )}

      <style dangerouslySetInnerHTML={{ __html: `
        svg { background-color: #ffffff; cursor: default; }
        .groups-layer path { transition: d 0.5s cubic-bezier(0.19, 1, 0.22, 1); }
        path { transition: stroke 0.3s ease; }
        text { pointer-events: none; user-select: none; }
      `}} />
    </div>
  );
};

export default App;