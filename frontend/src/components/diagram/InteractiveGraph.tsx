import { useEffect } from 'react';
import { ReactFlow, Background, Controls, MarkerType, useNodesState, useEdgesState, Position, Handle } from '@xyflow/react';
import type { Node, Edge } from '@xyflow/react';
import dagre from 'dagre';
import type { NormalizedSchema, NormalizedTable } from '../../lib/schema-adapter';
import '@xyflow/react/dist/style.css';

// Node Component
const TableNodeComponent = ({ data, targetPosition, sourcePosition }: { data: { table: NormalizedTable, isSelected: boolean }, targetPosition?: Position, sourcePosition?: Position }) => {
  const { table, isSelected } = data;

  return (
    <div className={`bg-white dark:bg-slate-900 border-2 rounded-xl shadow-lg min-w-[200px] overflow-hidden transition-colors ${isSelected ? 'border-blue-500 shadow-blue-500/20' : 'border-slate-200 dark:border-slate-700'}`}>
      <Handle type="target" position={targetPosition || Position.Left} className="w-2 h-2 bg-blue-500 border-2 border-white dark:border-slate-900" />
      
      <div className={`px-4 py-3 flex justify-between items-center ${isSelected ? 'bg-blue-50 dark:bg-blue-900/40 text-blue-800 dark:text-blue-200' : 'bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-slate-100'}`}>
        <h3 className="font-bold truncate pr-2 text-sm">{table.tableName}</h3>
        <div className="w-2 h-2 rounded-full bg-amber-500"></div>
      </div>

      <Handle type="source" position={sourcePosition || Position.Right} className="w-2 h-2 bg-blue-500 border-2 border-white dark:border-slate-900" />
    </div>
  );
};

const nodeTypes = {
  table: TableNodeComponent,
};

const getLayoutedElements = (nodes: Node[], edges: Edge[], direction = 'LR') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  const isHorizontal = direction === 'LR';
  dagreGraph.setGraph({ rankdir: direction, nodesep: 100, ranksep: 200 });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: 220, height: 60 }); // Appx dimensions for small node
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const newNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      targetPosition: isHorizontal ? Position.Left : Position.Top,
      sourcePosition: isHorizontal ? Position.Right : Position.Bottom,
      position: {
        x: nodeWithPosition.x - 220 / 2,
        y: nodeWithPosition.y - 60 / 2,
      },
    };
  });

  return { layoutedNodes: newNodes, layoutedEdges: edges };
};

interface InteractiveGraphProps {
  schema: NormalizedSchema;
  selectedTable: NormalizedTable | null;
  onNodeClick: (table: NormalizedTable) => void;
}

export const InteractiveGraph = ({ schema, selectedTable, onNodeClick }: InteractiveGraphProps) => {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  useEffect(() => {
    if (!selectedTable) {
      setNodes([]);
      setEdges([]);
      return;
    }

    const connectedTableNames = new Set<string>();
    connectedTableNames.add(selectedTable.tableName);
    
    selectedTable.relationships.forEach(r => connectedTableNames.add(r.parentTable));
    selectedTable.referencedBy.forEach(r => connectedTableNames.add(r.childTable));

    const initialNodes: Node[] = [];
    connectedTableNames.forEach(tName => {
      const table = schema.tables.find(t => t.tableName === tName);
      if (table) {
        initialNodes.push({
          id: table.tableName,
          type: 'table',
          position: { x: 0, y: 0 },
          data: { table, isSelected: table.tableName === selectedTable.tableName },
        });
      }
    });

    const initialEdges: Edge[] = [];
    schema.globalRelationships.forEach(rel => {
      if (connectedTableNames.has(rel.childTable) && connectedTableNames.has(rel.parentTable)) {
        initialEdges.push({
          id: `e-${rel.childTable}.${rel.childColumn}-${rel.parentTable}.${rel.parentColumn}`,
          source: rel.parentTable,
          target: rel.childTable,
          label: rel.name,
          type: 'smoothstep',
          animated: rel.childTable === selectedTable.tableName || rel.parentTable === selectedTable.tableName,
          style: { stroke: '#94a3b8', strokeWidth: 1.5 },
          labelStyle: { fill: '#64748b', fontWeight: 500, fontSize: 10 },
          labelBgStyle: { fill: '#f8fafc', fillOpacity: 0.8 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 20,
            height: 20,
            color: '#94a3b8',
          },
        });
      }
    });

    const { layoutedNodes, layoutedEdges } = getLayoutedElements(initialNodes, initialEdges, 'LR');
    setNodes(layoutedNodes);
    setEdges(layoutedEdges);
  }, [selectedTable, schema]);

  return (
    <div className="w-full h-full bg-slate-50/50 dark:bg-slate-950/50">
      <ReactFlow
        nodes={nodes as any}
        edges={edges as any}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={(_, node) => {
          const table = schema.tables.find(t => t.tableName === node.id);
          if (table) onNodeClick(table);
        }}
        nodeTypes={nodeTypes}
        fitView
        className="react-flow-container"
        minZoom={0.1}
        maxZoom={1.5}
      >
        <Background color="#cbd5e1" gap={16} />
        <Controls className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 fill-slate-700 dark:fill-slate-200" />
      </ReactFlow>
    </div>
  );
};
