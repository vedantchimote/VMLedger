import React, { useMemo, useCallback } from 'react';
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

  return (
    <div className="h-[600px] w-full border border-white/10 rounded-xl overflow-hidden bg-surface-900/50">
      <ReactFlow 
        nodes={nodes} 
        edges={edges} 
        nodeTypes={nodeTypes}
        fitView
        className="bg-surface-900"
      >
        <Background color="#374151" gap={16} size={1} />
        <Controls className="bg-surface-800 border-white/10 fill-white text-white" />
      </ReactFlow>
      <div className="absolute top-4 right-4 bg-surface-800/80 p-3 rounded-lg border border-white/10 backdrop-blur-md text-xs z-10">
        <div className="font-bold text-gray-300 mb-2">Legend</div>
        <div className="flex items-center gap-2 mb-1"><span className="w-3 h-3 bg-brand-500/20 border border-brand-500 block rounded-sm"></span> Host VM</div>
        <div className="flex items-center gap-2 mb-1"><span className="w-3 h-3 bg-purple-500/20 border border-purple-500 block rounded-sm"></span> Bridge / Switch</div>
        <div className="flex items-center gap-2 mb-1"><span className="w-3 h-3 bg-green-500/20 border border-green-500 block rounded-sm"></span> Running Container</div>
        <div className="flex items-center gap-2"><span className="w-3 h-3 bg-gray-500/20 border border-gray-500 block rounded-sm"></span> Stopped Container</div>
      </div>
    </div>
  );
}
