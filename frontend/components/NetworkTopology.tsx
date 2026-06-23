import React, { useMemo, useCallback, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ReactFlow, Background, Controls, Node, Edge, Position, Handle } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { api } from '@/lib/api-client';

// Custom Nodes
const HostNode = ({ data }: any) => (
  <div className="px-4 py-2 shadow-md rounded-md bg-brand-500/20 border-2 border-brand-500 min-w-[150px] text-center">
    <div className="font-bold text-white text-lg">💻 {data.label}</div>
    {data.ip && <div className="text-xs text-brand-300 mt-1">{data.ip}</div>}
    <Handle type="source" position={Position.Bottom} className="w-3 h-3 !bg-brand-500" />
  </div>
);

const BridgeNode = ({ data }: any) => (
  <div className="px-4 py-2 shadow-md rounded-md bg-purple-500/20 border-2 border-purple-500 min-w-[120px] text-center">
    <Handle type="target" position={Position.Top} className="w-3 h-3 !bg-purple-500" />
    <div className="font-bold text-white">🌉 {data.label}</div>
    <div className="text-xs text-purple-300">Bridge / Switch</div>
    <Handle type="source" position={Position.Bottom} className="w-3 h-3 !bg-purple-500" />
  </div>
);

const ContainerNode = ({ data }: any) => {
  const isRunning = data.status === 'running';
  const colorClass = isRunning ? "border-green-500 bg-green-500/10" : "border-gray-500 bg-gray-500/10";
  const textClass = isRunning ? "text-green-400" : "text-gray-400";
  
  return (
    <div className={`px-4 py-3 shadow-md rounded-md border-2 ${colorClass} min-w-[160px]`}>
      <Handle type="target" position={Position.Top} className={`w-3 h-3 !bg-gray-400`} />
      <div className="flex justify-between items-center mb-1">
        <div className={`font-bold text-sm ${isRunning ? 'text-white' : 'text-gray-300'}`}>📦 {data.label}</div>
        <div className={`w-2 h-2 rounded-full ${isRunning ? 'bg-green-500' : 'bg-red-500'}`} title={data.status}></div>
      </div>
      <div className={`text-xs font-mono mt-2 ${textClass}`}>
        {data.ip || 'No IP detected'}
      </div>
    </div>
  );
};

const nodeTypes = {
  host: HostNode,
  bridge: BridgeNode,
  container: ContainerNode,
};

interface NetworkTopologyProps {
  vmId: number;
}

export function NetworkTopology({ vmId }: NetworkTopologyProps) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['network-topology', vmId],
    queryFn: () => api.network.getTopology(vmId),
    refetchInterval: 30000,
  });

  const { nodes, edges } = useMemo(() => {
    if (!data) return { nodes: [], edges: [] };
    
    // Simple tree layout algorithm
    const layoutNodes: Node[] = [];
    const layoutEdges: Edge[] = [];
    
    // Add edges
    data.edges.forEach(e => {
      layoutEdges.push({
        id: e.id,
        source: e.source,
        target: e.target,
        animated: true,
        style: { stroke: '#4b5563', strokeWidth: 2 },
      });
    });

    // Positions mapping
    const hostNode = data.nodes.find(n => n.type === 'host');
    const bridgeNodes = data.nodes.filter(n => n.type === 'bridge');
    const containerNodes = data.nodes.filter(n => n.type === 'container');
    
    let yLevel = 50;
    
    if (hostNode) {
      layoutNodes.push({
        id: hostNode.id,
        type: 'host',
        position: { x: 400, y: yLevel },
        data: { label: hostNode.label, ip: hostNode.ip },
      });
    }
    
    yLevel += 150;
    const bridgeSpacing = 300;
    const startX = 400 - ((bridgeNodes.length - 1) * bridgeSpacing) / 2;
    
    bridgeNodes.forEach((bridge, idx) => {
      layoutNodes.push({
        id: bridge.id,
        type: 'bridge',
        position: { x: startX + (idx * bridgeSpacing), y: yLevel },
        data: { label: bridge.label },
      });
      
      // Find containers connected to this bridge
      const connectedEdges = data.edges.filter(e => e.source === bridge.id);
      const connectedContainerIds = connectedEdges.map(e => e.target);
      const connectedContainers = containerNodes.filter(c => connectedContainerIds.includes(c.id));
      
      const cSpacing = 200;
      const cStart = (startX + (idx * bridgeSpacing)) - ((connectedContainers.length - 1) * cSpacing) / 2;
      
      connectedContainers.forEach((c, cIdx) => {
        layoutNodes.push({
          id: c.id,
          type: 'container',
          position: { x: cStart + (cIdx * cSpacing), y: yLevel + 150 },
          data: { label: c.label, ip: c.ip, status: c.status },
        });
      });
    });
    
    // Add unlinked containers just in case
    const linkedIds = layoutNodes.map(n => n.id);
    const unlinkedContainers = containerNodes.filter(c => !linkedIds.includes(c.id));
    unlinkedContainers.forEach((c, cIdx) => {
      layoutNodes.push({
        id: c.id,
        type: 'container',
        position: { x: 100 + (cIdx * 200), y: yLevel + 300 },
        data: { label: c.label, ip: c.ip, status: c.status },
      });
    });

    return { nodes: layoutNodes, edges: layoutEdges };
  }, [data]);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-96 text-gray-400 space-y-4">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
        <p>Scanning network topology via SSH...</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center h-96 text-red-400 space-y-4 bg-surface-800/30 rounded-xl border border-white/5">
        <p>Failed to load network topology.</p>
        <button onClick={() => refetch()} className="px-4 py-2 bg-surface-700 text-white rounded hover:bg-surface-600 transition">
          Retry
        </button>
      </div>
    );
  }

  const content = (
    <div className={`${isFullscreen ? 'fixed inset-0 z-[9999] h-screen w-screen rounded-none bg-surface-900/95 backdrop-blur-xl' : 'relative h-[600px] w-full rounded-xl bg-surface-900/50'} border border-white/10 overflow-hidden transition-all duration-300`}>
      <button 
        onClick={() => setIsFullscreen(!isFullscreen)}
        className="absolute top-6 left-6 z-10 px-3 py-1.5 bg-surface-800/80 border border-white/10 rounded-md text-xs font-medium text-gray-300 hover:text-white hover:bg-surface-700 shadow-lg backdrop-blur-md transition-colors flex items-center gap-1.5"
      >
        {isFullscreen ? (
          <>
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
            Exit Fullscreen
          </>
        ) : (
          <>
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" /></svg>
            Fullscreen
          </>
        )}
      </button>

      <ReactFlow 
        key={isFullscreen ? 'fullscreen' : 'normal'}
        nodes={nodes} 
        edges={edges} 
        nodeTypes={nodeTypes}
        fitView
        className="bg-surface-900"
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#374151" gap={16} size={1} />
        <Controls 
          position="bottom-right"
          className="!absolute !bottom-6 !right-8 !left-auto !bg-surface-800 !border-white/10 !shadow-lg [&>button]:!bg-surface-800 [&>button]:!border-b-white/5 [&>button:hover]:!bg-surface-700 [&_svg]:!fill-gray-300" 
        />
      </ReactFlow>
      <div className="absolute top-6 right-8 bg-surface-800/80 p-3 rounded-lg border border-white/10 backdrop-blur-md text-xs z-10 shadow-lg">
        <div className="font-bold text-gray-300 mb-2">Legend</div>
        <div className="flex items-center gap-2 mb-1"><span className="w-3 h-3 bg-brand-500/20 border border-brand-500 block rounded-sm"></span> Host VM</div>
        <div className="flex items-center gap-2 mb-1"><span className="w-3 h-3 bg-purple-500/20 border border-purple-500 block rounded-sm"></span> Bridge / Switch</div>
        <div className="flex items-center gap-2 mb-1"><span className="w-3 h-3 bg-green-500/20 border border-green-500 block rounded-sm"></span> Running Container</div>
        <div className="flex items-center gap-2"><span className="w-3 h-3 bg-gray-500/20 border border-gray-500 block rounded-sm"></span> Stopped Container</div>
      </div>
    </div>
  );

  if (isFullscreen && typeof document !== 'undefined') {
    import('react-dom').then((ReactDOM) => {
      // Using dynamic import for react-dom to avoid SSR issues with document
    });
    const { createPortal } = require('react-dom');
    return (
      <>
        {/* Placeholder to preserve the page layout when the map is popped out */}
        <div className="h-[600px] w-full border border-white/5 rounded-xl bg-surface-800/20 animate-pulse flex items-center justify-center text-gray-500">
          Network Topology is open in Fullscreen
        </div>
        {createPortal(content, document.body)}
      </>
    );
  }

  return content;
}
