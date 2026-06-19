import {
  addEdge,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  useReactFlow,
} from '@xyflow/react'
import type {
  Connection,
  EdgeChange,
  NodeChange,
  NodeMouseHandler,
  OnConnect,
  OnNodesDelete,
} from '@xyflow/react'
import { useEffect, useRef, useState } from 'react'
import type { Dispatch, DragEvent, MouseEvent, SetStateAction } from 'react'

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
  gitCommit: StatusNode,
  sshCommand: StatusNode,
  httpRequest: StatusNode,
  condition: StatusNode,
  notify: StatusNode,
  delay: StatusNode,
}

const labels: Record<string, string> = {
  manualTrigger: 'Manual Trigger',
  shell: 'Shell',
  gitCommit: 'Git Commit',
  sshCommand: 'SSH Command',
  httpRequest: 'HTTP Request',
  condition: 'Condition',
  notify: 'Notify',
  delay: 'Delay',
}

type ContextMenuState = {
  nodeId: string
  x: number
  y: number
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
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null)
  const contextMenuRef = useRef<HTMLDivElement | null>(null)

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

    const defaults: Record<string, unknown> = {}
    if (type === 'gitCommit') {
      defaults.addAll = true
      defaults.commit = true
      defaults.push = false
      defaults.remote = 'origin'
    } else if (type === 'sshCommand') {
      defaults.port = 22
      defaults.timeout = 30
    }

    setNodes((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        type,
        position,
        data: { label, status: 'pending', ...defaults },
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
    setContextMenu(null)
  }

  const closeContextMenu = () => setContextMenu(null)

  const onNodeContextMenu: NodeMouseHandler<WorkflowNode> = (event, node) => {
    event.preventDefault()
    onSelectNode(node.id)
    setContextMenu({ nodeId: node.id, x: event.clientX, y: event.clientY })
  }

  const duplicateNode = () => {
    if (!contextMenu) return
    setNodes((current) => {
      const nodeToDuplicate = current.find((node) => node.id === contextMenu.nodeId)
      if (!nodeToDuplicate) return current
      const duplicatedId = crypto.randomUUID()
      onSelectNode(duplicatedId)
      return [
        ...current,
        {
          ...nodeToDuplicate,
          id: duplicatedId,
          position: {
            x: nodeToDuplicate.position.x + 40,
            y: nodeToDuplicate.position.y + 40,
          },
          selected: false,
          data: { ...nodeToDuplicate.data },
        },
      ]
    })
    closeContextMenu()
  }

  const deleteNode = () => {
    if (!contextMenu) return
    const nodeId = contextMenu.nodeId
    setNodes((current) => current.filter((node) => node.id !== nodeId))
    setEdges((current) => current.filter((edge) => edge.source !== nodeId && edge.target !== nodeId))
    if (selectedNodeId === nodeId) {
      onSelectNode(null)
    }
    closeContextMenu()
  }

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setContextMenu(null)
      }
    }

    const onMouseDown = (event: globalThis.MouseEvent) => {
      if (event.button !== 0) return
      if (contextMenuRef.current?.contains(event.target as Node)) return
      setContextMenu(null)
    }

    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('mousedown', onMouseDown)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('mousedown', onMouseDown)
    }
  }, [])

  const onCanvasMouseDown = (event: MouseEvent<HTMLDivElement>) => {
    if (event.button === 0) {
      closeContextMenu()
    }
  }

  return (
    <div className="canvas" onDrop={onDrop} onDragOver={onDragOver} onMouseDown={onCanvasMouseDown}>
      <ReactFlow
        nodes={displayNodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={rfNodeTypes}
        fitView
        onNodeClick={(_, node) => onSelectNode(node.id)}
        onNodeContextMenu={onNodeContextMenu}
        onPaneClick={() => {
          onSelectNode(null)
          closeContextMenu()
        }}
        onNodesDelete={onNodesDelete}
      >
        <MiniMap />
        <Controls />
        <Background gap={16} variant={BackgroundVariant.Dots} />
      </ReactFlow>
      {contextMenu ? (
        <div
          ref={contextMenuRef}
          className="node-context-menu"
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          <button
            type="button"
            className="node-context-menu-item"
            onClick={() => {
              onSelectNode(contextMenu.nodeId)
              closeContextMenu()
            }}
          >
            Modifier
          </button>
          <button type="button" className="node-context-menu-item" onClick={duplicateNode}>
            Dupliquer
          </button>
          <button type="button" className="node-context-menu-item danger" onClick={deleteNode}>
            Supprimer
          </button>
        </div>
      ) : null}
    </div>
  )
}
