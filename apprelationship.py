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
const appId = typeof __app_id !== 'undefined' ? __app_id : 'org-chart-gen-004'; // 升級版本

// 預設頭像 (使用 SVG Base64 避免下載破圖與跨域問題)
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
  
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const simulationRef = useRef(null);

  // 動態載入 html2canvas
  useEffect(() => {
    const script = document.createElement('script');
    script.src = "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js";
    script.async = true;
    script.onload = () => setLibLoaded(true);
    document.body.appendChild(script);
    return () => { if (document.body.contains(script)) document.body.removeChild(script); };
  }, []);

  // Firebase 認證
  useEffect(() => {
    const initAuth = async () => {
      try {
        if (typeof __initial_auth_token !== 'undefined' && __initial_auth_token) {
          await signInWithCustomToken(auth, __initial_auth_token);
        } else {
          await signInAnonymously(auth);
        }
      } catch (err) { console.error("認證失敗:", err); }
    };
    initAuth();
    const unsubscribeAuth = onAuthStateChanged(auth, setUser);
    return () => unsubscribeAuth();
  }, []);

  // Firestore 資料監聽
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

  // --- D3 渲染核心 ---
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

    // 箭頭定義
    const defs = svg.append("defs");
    defs.append("marker")
      .attr("id", "arrow-end")
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 38) // 配合半徑微調
      .attr("refY", 0)
      .attr("orient", "auto").attr("markerWidth", 6).attr("markerHeight", 6)
      .append("path").attr("d", "M0,-5L10,0L0,5").attr("fill", "#94a3b8");
    
    defs.append("marker")
      .attr("id", "arrow-start")
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", -28) // 配合半徑微調
      .attr("refY", 0)
      .attr("orient", "auto").attr("markerWidth", 6).attr("markerHeight", 6)
      .append("path").attr("d", "M10,-5L0,0L10,5").attr("fill", "#94a3b8");

    const groupLayer = g.append("g").attr("class", "groups-layer");

    // 連線組件
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
      .attr("font-size", "11px")
      .attr("font-weight", "bold")
      .attr("fill", "#64748b")
      .attr("text-anchor", "middle")
      // 加上白色發光邊框讓文字在壓線時依然清晰
      .style("paint-order", "stroke")
      .style("stroke", "#ffffff")
      .style("stroke-width", "3px")
      .style("stroke-linecap", "round")
      .style("stroke-linejoin", "round")
      .text(d => d.label || "");

    // 節點組件
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
      .attr("xlink:href", d => d.avatar || DEFAULT_AVATAR)
      .attr("x", -30).attr("y", -30).attr("width", 60).attr("height", 60)
      .attr("clip-path", d => `url(#clip-${d.id})`)
      .on("error", function() { d3.select(this).attr("xlink:href", DEFAULT_AVATAR); });

    nodeElements.append("text")
      .attr("dy", 50).attr("text-anchor", "middle").attr("font-weight", "600").attr("font-size", "12px")
      .attr("fill", "#1e293b").text(d => d.name);

    // 物理力模擬設定
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

    // --- 安全的取得節點座標方法 (解決線脫離的核心) ---
    function getNodeCoord(ref) {
      if (!ref) return { x: 0, y: 0 };
      const id = typeof ref === 'object' ? ref.id : ref;
      // 強制從當前的 nodes 陣列中尋找最新座標
      return nodes.find(n => n.id === id) || (typeof ref === 'object' ? ref : { x: 0, y: 0 });
    }

    function ticked() {
      // 處理多連線弧度與同步 (解決線黏在一起)
      const linkGroups = {};
      links.forEach(l => {
        const sId = typeof l.source === 'object' ? l.source.id : l.source;
        const tId = typeof l.target === 'object' ? l.target.id : l.target;
        // 把節點對用統一的方式排序，當作群組 key
        const pair = [sId, tId].sort().join("-");
        if (!linkGroups[pair]) linkGroups[pair] = [];
        linkGroups[pair].push(l);
      });

      linkElements.attr("d", d => {
        const s = getNodeCoord(d.source);
        const t = getNodeCoord(d.target);
        if (!s.id || !t.id) return ""; // 安全防護

        const sId = s.id, tId = t.id;
        const pair = [sId, tId].sort().join("-");
        const group = linkGroups[pair];
        const idx = group.indexOf(d);
        const count = group.length;
        
        const dx = t.x - s.x;
        const dy = t.y - s.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (count === 1 || dist === 0) {
          // 只有一條線時畫直線
          return `M${s.x},${s.y}L${t.x},${t.y}`;
        } else {
          // 多條線時計算弧線。dr 越小彎度越大。
          const curveFactor = 1.1 + Math.floor(idx / 2) * 0.4;
          const dr = dist * curveFactor;
          // 利用 sweep-flag 決定往哪邊彎。確保同組線彼此避開。
          const sweep = idx % 2 === 0 ? 1 : 0;
          return `M${s.x},${s.y} A${dr},${dr} 0 0,${sweep} ${t.x},${t.y}`;
        }
      });

      linkLabels.attr("transform", d => {
        const s = getNodeCoord(d.source);
        const t = getNodeCoord(d.target);
        const pair = [s.id, t.id].sort().join("-");
        const idx = (linkGroups[pair] || []).indexOf(d);
        const count = (linkGroups[pair] || []).length;
        
        const x = (s.x + t.x) / 2;
        const y = (s.y + t.y) / 2;
        
        // 依照連線順序稍微錯開文字的 Y 軸位置
        let yOffset = -10;
        if (count > 1) {
           yOffset = idx % 2 === 0 ? -15 - (Math.floor(idx/2)*12) : 15 + (Math.floor(idx/2)*12);
        }
        return `translate(${x},${y + yOffset})`;
      });

      nodeElements.attr("transform", d => `translate(${d.x},${d.y})`);

      // 秘密結社繪製
      groupLayer.selectAll("path").remove();
      groups.forEach(gData => {
        const gNodes = nodes.filter(n => gData.memberIds?.includes(n.id));
        if (gNodes.length === 0) return;
        const pts = gNodes.map(n => [n.x, n.y]);
        let pStr = "";
        if (pts.length === 1) {
          pStr = `M ${pts[0][0]-65},${pts[0][1]} a 65,65 0 1,0 130,0 a 65,65 0 1,0 -130,0`;
        } else if (pts.length === 2) {
          const [x1, y1] = pts[0], [x2, y2] = pts[1], dx = x2-x1, dy = y2-y1, len = Math.sqrt(dx*dx+dy*dy);
          const off = 65, nx = dy/len*off, ny = -dx/len*off;
          pStr = `M ${x1+nx},${y1+ny} L ${x2+nx},${y2+ny} A ${off},${off} 0 0 1 ${x2-nx},${y2-ny} L ${x1-nx},${y1-ny} A ${off},${off} 0 0 1 ${x1+nx},${y1+ny}`;
        } else {
          const hull = d3.polygonHull(pts);
          if (hull) pStr = d3.line().curve(d3.curveBasisClosed)(hull);
        }
        groupLayer.append("path").attr("d", pStr).attr("fill", gData.color).attr("fill-opacity", 0.1).attr("stroke", gData.color).attr("stroke-width", 2).attr("stroke-dasharray", "6 4").lower();
      });
    }

    function dragstarted(event) {
      if (viewMode === 'flat') return;
      if (!event.active) simulation.alphaTarget(0.3).restart();
      event.subject.fx = event.subject.x;
      event.subject.fy = event.subject.y;
    }

    function dragged(event) {
      // **關鍵修復**：拖拽中絕對不要呼叫 updateDoc，否則會觸發 React 重繪導致線條脫離
      if (viewMode === 'flat') {
        const targetNode = nodes.find(n => n.id === event.subject.id);
        if (targetNode) {
          targetNode.x = event.x;
          targetNode.y = event.y;
        }
        event.subject.x = event.x;
        event.subject.y = event.y;
        ticked(); // 強制重繪當前幀
      } else {
        event.subject.fx = event.x;
        event.subject.fy = event.y;
      }
    }

    function dragended(event) {
      // 只有在「放開拖曳」的最後一刻，才將座標寫回 Firestore
      if (viewMode === 'flat') {
        updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'nodes', event.subject.id), { x: event.subject.x, y: event.subject.y });
      } else {
        if (!event.active) simulation.alphaTarget(0);
        event.subject.fx = null; 
        event.subject.fy = null;
        updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'nodes', event.subject.id), { x: event.subject.x, y: event.subject.y });
      }
    }
  }, [nodes, links, groups, viewMode, selectedNode]);

  // --- 操作邏輯 ---

  const handleAddNode = async () => {
    const id = crypto.randomUUID();
    await setDoc(doc(db, 'artifacts', appId, 'public', 'data', 'nodes', id), { name: "新成員", avatar: "", x: 400, y: 300 });
  };

  const handleDeleteNode = async (id) => {
    await deleteDoc(doc(db, 'artifacts', appId, 'public', 'data', 'nodes', id));
    links.forEach(async l => {
      const sId = l.source.id || l.source, tId = l.target.id || l.target;
      if (sId === id || tId === id) await deleteDoc(doc(db, 'artifacts', appId, 'public', 'data', 'links', l.id));
    });
    setSelectedNode(null);
  };

  const handleAddLink = async (targetId) => {
    if (!selectedNode || selectedNode.id === targetId) return;
    const id = crypto.randomUUID();
    await setDoc(doc(db, 'artifacts', appId, 'public', 'data', 'links', id), { source: selectedNode.id, target: targetId, type: 'unidirectional', label: '新關係' });
  };

  const handleAddGroup = async () => {
    const id = crypto.randomUUID();
    await setDoc(doc(db, 'artifacts', appId, 'public', 'data', 'groups', id), {
      name: "新秘密結社", 
      color: "#" + Math.floor(Math.random()*16777215).toString(16), 
      memberIds: []
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
    const canvas = await window.html2canvas(containerRef.current, {
      backgroundColor: '#ffffff',
      useCORS: true,
      allowTaint: true,
      scale: 2,
      logging: false
    });
    const link = document.createElement('a');
    link.download = `組織圖_${Date.now()}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
  };

  const handleAvatarFile = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (ev) => { setTempAvatar(ev.target.result); setAvatarModalOpen(true); };
      reader.readAsDataURL(file);
    }
  };

  const handleSaveAvatar = async () => {
    if (selectedNode && tempAvatar) {
      await updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'nodes', selectedNode.id), { avatar: tempAvatar });
      setAvatarModalOpen(false); setTempAvatar(null);
    }
  };

  return (
    <div className="flex h-screen w-full bg-slate-50 text-slate-900 overflow-hidden font-sans">
      {/* 側邊欄 */}
      <aside className={`bg-white border-r border-slate-200 transition-all duration-300 flex flex-col z-30 shadow-2xl ${isSidebarOpen ? 'w-80' : 'w-0 overflow-hidden'}`}>
        <div className="p-4 bg-indigo-600 text-white flex justify-between items-center">
          <h1 className="font-bold flex items-center gap-2 text-lg"><Users size={20} /> 組織生成器</h1>
          <button onClick={() => setSidebarOpen(false)} className="hover:bg-indigo-700 p-1 rounded"><X size={18} /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          <section className="space-y-2">
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest">新增元件</h2>
            <div className="grid grid-cols-2 gap-2">
              <button onClick={handleAddNode} className="flex items-center justify-center gap-2 bg-indigo-50 text-indigo-700 py-2.5 rounded-xl hover:bg-indigo-100 text-sm font-bold transition-all shadow-sm"><UserPlus size={16} /> 新角色</button>
              <button onClick={handleAddGroup} className="flex items-center justify-center gap-2 bg-slate-100 text-slate-700 py-2.5 rounded-xl hover:bg-slate-200 text-sm font-bold transition-all shadow-sm"><Hexagon size={16} /> 新結社</button>
            </div>
          </section>

          {selectedNode ? (
            <section className="bg-slate-50 p-4 rounded-2xl border border-slate-200 space-y-4 animate-in slide-in-from-right duration-200 shadow-inner">
              <div className="flex justify-between items-center">
                <h2 className="font-bold text-slate-700">編輯角色：{selectedNode.name}</h2>
                <button onClick={() => handleDeleteNode(selectedNode.id)} className="text-red-400 hover:text-red-600 p-1.5"><Trash2 size={18} /></button>
              </div>
              <div className="space-y-4">
                <input type="text" value={selectedNode.name} onChange={(e) => updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'nodes', selectedNode.id), { name: e.target.value })} className="w-full rounded-xl border-slate-200 px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-100 outline-none shadow-sm" placeholder="角色名稱" />
                <div className="flex items-center gap-4">
                  <img src={selectedNode.avatar || DEFAULT_AVATAR} className="w-16 h-16 rounded-full border-4 border-white shadow-md object-cover bg-white" alt="avatar" />
                  <label className="cursor-pointer bg-white border border-slate-200 px-4 py-2 rounded-xl text-xs font-bold hover:bg-slate-50 shadow-sm">
                    更換頭像 <input type="file" className="hidden" accept="image/*" onChange={handleAvatarFile} />
                  </label>
                </div>
                <div className="space-y-2">
                  <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">建立新關係 (點選目標)</span>
                  <div className="flex flex-wrap gap-2">
                    {nodes.filter(n => n.id !== selectedNode.id).map(n => (
                      <button key={n.id} onClick={() => handleAddLink(n.id)} className="text-[10px] bg-white border border-indigo-100 text-indigo-600 px-2.5 py-1.5 rounded-full hover:bg-indigo-50 font-bold shadow-xs">+ {n.name}</button>
                    ))}
                  </div>
                </div>
                <div className="space-y-2">
                  <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">現有關係管理</span>
                  <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                    {links.filter(l => {
                      const sid = l.source.id || l.source;
                      const tid = l.target.id || l.target;
                      return sid === selectedNode.id || tid === selectedNode.id;
                    }).map(l => {
                      const sid = l.source.id || l.source, tid = l.target.id || l.target;
                      const targetNode = nodes.find(n => n.id === (sid === selectedNode.id ? tid : sid));
                      return (
                        <div key={l.id} className="flex items-center justify-between bg-white p-2 rounded-xl border border-slate-100 shadow-xs">
                          <div className="flex flex-col">
                            <span className="text-[10px] text-slate-400">對應：{targetNode?.name}</span>
                            <input type="text" value={l.label} onChange={(e) => updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'links', l.id), { label: e.target.value })} className="text-[11px] font-bold border-0 p-0 focus:ring-0 w-20 bg-transparent" />
                          </div>
                          <div className="flex gap-1">
                            <button onClick={() => updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'links', l.id), { type: l.type === 'unidirectional' ? 'bidirectional' : 'unidirectional' })} className={`p-1.5 rounded-lg transition-all ${l.type === 'bidirectional' ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-400'}`}><ArrowRightLeft size={12} /></button>
                            <button onClick={() => deleteDoc(doc(db, 'artifacts', appId, 'public', 'data', 'links', l.id))} className="p-1.5 bg-red-50 text-red-400 rounded-lg"><Trash2 size={12} /></button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </section>
          ) : (
            <div className="text-center py-24 border-2 border-dashed border-slate-100 rounded-[40px]">
              <Move className="mx-auto mb-4 text-slate-200" size={48} />
              <p className="text-sm text-slate-300 font-bold">點選角色開始編輯</p>
            </div>
          )}

          <section className="space-y-3">
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest">秘密結社 (小圈圈)</h2>
            {groups.map(g => (
              <div key={g.id} className="p-4 bg-white border border-slate-200 rounded-2xl flex items-center justify-between shadow-sm group hover:border-indigo-200 transition-all">
                <div className="flex items-center gap-3">
                  <input type="color" value={g.color} onChange={(e) => updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'groups', g.id), { color: e.target.value })} className="w-8 h-8 rounded-lg border-0 p-0 cursor-pointer shadow-sm" />
                  <input type="text" value={g.name} onChange={(e) => updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'groups', g.id), { name: e.target.value })} className="text-sm font-bold border-0 p-0 focus:ring-0 w-32 bg-transparent text-slate-700" />
                </div>
                <div className="flex gap-1 items-center opacity-0 group-hover:opacity-100 transition-all">
                   <input type="checkbox" checked={selectedNode && g.memberIds?.includes(selectedNode.id)} onChange={() => selectedNode && handleToggleGroup(g.id, selectedNode.id)} className="w-4 h-4 text-indigo-600 cursor-pointer" title="加入/退出結社" />
                   <button onClick={() => deleteDoc(doc(db, 'artifacts', appId, 'public', 'data', 'groups', g.id))} className="text-slate-300 hover:text-red-500 p-1"><Trash2 size={14} /></button>
                </div>
              </div>
            ))}
          </section>
        </div>
      </aside>

      {/* 主畫布區 */}
      <main className="flex-1 relative bg-slate-50">
        <div className="absolute top-6 left-6 z-20 flex gap-3">
          {!isSidebarOpen && (
            <button onClick={() => setSidebarOpen(true)} className="bg-white p-3 rounded-2xl shadow-xl border border-slate-200 text-indigo-600 hover:scale-105 transition-all"><Settings2 size={24} /></button>
          )}
          <div className="flex bg-white rounded-2xl shadow-xl border border-slate-200 p-1.5">
            <button onClick={() => setViewMode('force')} className={`px-6 py-2.5 rounded-xl text-sm font-black transition-all ${viewMode === 'force' ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-400 hover:bg-slate-50'}`}>物理引力</button>
            <button onClick={() => setViewMode('flat')} className={`px-6 py-2.5 rounded-xl text-sm font-black transition-all ${viewMode === 'flat' ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-400 hover:bg-slate-50'}`}>自由定位</button>
          </div>
        </div>

        <div className="absolute top-6 right-6 z-20">
           <button disabled={!libLoaded} onClick={handleDownload} className="flex items-center gap-2 bg-slate-900 text-white px-7 py-3.5 rounded-2xl shadow-2xl hover:bg-black font-black text-sm transition-all active:scale-95 disabled:opacity-50"><Download size={20} /> 匯出圖檔</button>
        </div>

        <div ref={containerRef} className="flex-1 h-full bg-white relative overflow-hidden">
          <svg ref={svgRef} className="w-full h-full" onClick={(e) => e.target.tagName === 'svg' && setSelectedNode(null)} />
        </div>
      </main>

      {/* 頭像裁切彈窗 */}
      {isAvatarModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-md z-50 flex items-center justify-center p-6 animate-in fade-in duration-300">
          <div className="bg-white rounded-[40px] shadow-2xl max-w-sm w-full p-10 animate-in zoom-in duration-200">
            <div className="text-center mb-8"><h3 className="text-2xl font-black text-slate-800 tracking-tight">裁切預覽</h3></div>
            <div className="relative aspect-square w-full rounded-full overflow-hidden border-[12px] border-indigo-50 bg-slate-50 mb-10 mx-auto max-w-[240px] shadow-inner ring-1 ring-slate-200">
              {tempAvatar && <img src={tempAvatar} className="w-full h-full object-cover" alt="preview" />}
            </div>
            <div className="flex gap-4">
              <button onClick={() => setAvatarModalOpen(false)} className="flex-1 py-4 rounded-[20px] border-2 border-slate-100 font-bold text-slate-400">取消</button>
              <button onClick={handleSaveAvatar} className="flex-1 py-4 rounded-[20px] bg-indigo-600 text-white font-bold shadow-xl shadow-indigo-100 hover:bg-indigo-700 flex items-center justify-center gap-2"><Check size={20} /> 儲存</button>
            </div>
          </div>
        </div>
      )}

      <style dangerouslySetInnerHTML={{ __html: `
        svg { background-color: #ffffff; cursor: default; }
        .groups-layer path { transition: d 0.5s cubic-bezier(0.19, 1, 0.22, 1); }
        text { pointer-events: none; user-select: none; }
      `}} />
    </div>
  );
};

export default App;