import {
  addEdge,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  useReactFlow,
} from '@xyflow/react'
import type { Connection, EdgeChange, NodeChange, OnConnect, OnNodesDelete } from '@xyflow/react'
import type { Dispatch, DragEvent, SetStateAction } from 'react'

import type { NodeStatus, WorkflowEdge, WorkflowNode } from '../types'
import StatusNode from './nodes/StatusNode'

type Props = {
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  nodeStatuses: Record<string, NodeStatus>
  selectedNodeId: string | null
  onNodesChange: (changes: NodeChange<WorkflowNode>[]) => void
  onEdgesChange: (changes: EdgeChange<WorkflowEdge>[]) => void
  setNodes: Dispatch<SetStateAction<WorkflowNode[]>>
  setEdges: Dispatch<SetStateAction<WorkflowEdge[]>>
  onSelectNode: (nodeId: string | null) => void
}

const rfNodeTypes = {
  manualTrigger: StatusNode,
  shell: StatusNode,
  httpRequest: StatusNode,
  condition: StatusNode,
  notify: StatusNode,
  delay: StatusNode,
}

const labels: Record<string, string> = {
  manualTrigger: 'Manual Trigger',
  shell: 'Shell',
  httpRequest: 'HTTP Request',
  condition: 'Condition',
  notify: 'Notify',
  delay: 'Delay',
}

export default function Canvas({
  nodes,
  edges,
  nodeStatuses,
  selectedNodeId,
  onNodesChange,
  onEdgesChange,
  setNodes,
  setEdges,
  onSelectNode,
}: Props) {
  const { screenToFlowPosition } = useReactFlow()

  const onConnect: OnConnect = (params: Connection) => {
    let condition: 'success' | 'failure' | undefined
    const sourceNode = nodes.find((node) => node.id === params.source)
    if (sourceNode?.type === 'condition') {
      const selected = window.prompt("Condition edge branch (success/failure)", 'success')
      condition = selected === 'failure' ? 'failure' : 'success'
    }
    setEdges((current) => addEdge({ ...params, id: crypto.randomUUID(), on: condition }, current))
  }

  const onDrop = (event: DragEvent) => {
    event.preventDefault()
    const type = event.dataTransfer.getData('application/reactflow')
    if (!type) return

    const position = screenToFlowPosition({ x: event.clientX, y: event.clientY })
    const label = labels[type] || type

    setNodes((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        type,
        position,
        data: { label, status: 'pending' },
      },
    ])
  }

  const onDragOver = (event: DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }

  const displayNodes = nodes.map((node) => ({
    ...node,
    selected: node.id === selectedNodeId,
    data: { ...node.data, status: nodeStatuses[node.id] ?? 'pending' },
  }))

  const onNodesDelete: OnNodesDelete<WorkflowNode> = (deletedNodes) => {
    setEdges((current) =>
      current.filter(
        (edge) => !deletedNodes.some((node) => node.id === edge.source || node.id === edge.target),
      ),
    )
  }

  return (
    <div className="canvas" onDrop={onDrop} onDragOver={onDragOver}>
      <ReactFlow
        nodes={displayNodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={rfNodeTypes}
        fitView
        onNodeClick={(_, node) => onSelectNode(node.id)}
        onPaneClick={() => onSelectNode(null)}
        onNodesDelete={onNodesDelete}
      >
        <MiniMap />
        <Controls />
        <Background gap={16} variant={BackgroundVariant.Dots} />
      </ReactFlow>
    </div>
  )
}
