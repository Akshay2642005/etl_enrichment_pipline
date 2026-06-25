import { useMemo } from 'react';
import { ReactFlow, Background, Controls, MiniMap, MarkerType } from '@xyflow/react';
import type { Node, Edge } from '@xyflow/react';
import dagre from 'dagre';
import type { Database } from '../../models/metadata';
import { TableNode } from './TableNode';
import '@xyflow/react/dist/style.css';

const nodeTypes = {
  table: TableNode,
};

const getLayoutedElements = (nodes: Node[], edges: Edge[], direction = 'LR') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  
  const isHorizontal = direction === 'LR';
  dagreGraph.setGraph({ rankdir: direction, nodesep: 100, ranksep: 200 });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: 280, height: 300 }); // Appx dimensions
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const newNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      targetPosition: isHorizontal ? 'left' : 'top',
      sourcePosition: isHorizontal ? 'right' : 'bottom',
      position: {
        x: nodeWithPosition.x - 280 / 2,
        y: nodeWithPosition.y - 300 / 2,
      },
    };
  });

  return { nodes: newNodes, edges };
};

export const ERDiagram = ({ database }: { database: Database }) => {
  const { nodes: initialNodes, edges: initialEdges } = useMemo(() => {
    const nodes: Node[] = database.tables.map((table) => ({
      id: table.table_name,
      type: 'table',
      position: { x: 0, y: 0 },
      data: { table },
    }));

    const edges: Edge[] = [];
    database.tables.forEach((table) => {
      table.relationships?.forEach((rel) => {
        edges.push({
          id: `${table.table_name}-${rel.child_column}-${rel.parent_table}-${rel.parent_column}`,
          source: rel.parent_table,
          target: table.table_name,
          sourceHandle: `source-${rel.parent_column}`,
          targetHandle: `target-${rel.child_column}`,
          type: 'smoothstep',
          animated: true,
          style: { stroke: '#94a3b8', strokeWidth: 1.5 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 20,
            height: 20,
            color: '#94a3b8',
          },
        });
      });
    });

    return getLayoutedElements(nodes, edges, 'LR');
  }, [database]);

  return (
    <div className="w-full h-full bg-slate-50 dark:bg-slate-950/50 rounded-xl border border-slate-200 dark:border-slate-800">
      <ReactFlow
        nodes={initialNodes as any}
        edges={initialEdges as any}
        nodeTypes={nodeTypes}
        fitView
        className="react-flow-container"
        minZoom={0.1}
      >
        <Background color="#cbd5e1" gap={16} />
        <Controls className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 fill-slate-700 dark:fill-slate-200" />
        <MiniMap 
          className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700" 
          maskColor="rgba(248, 250, 252, 0.7)"
        />
      </ReactFlow>
    </div>
  );
};
