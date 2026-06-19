import { useCallback, useMemo, useRef, useState } from 'react'
import {
  ReactFlowProvider,
  applyEdgeChanges,
  applyNodeChanges,
} from '@xyflow/react'
import type { EdgeChange, NodeChange } from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { api } from './api/client'
import { useExecutionSocket } from './api/useExecutionSocket'
import Canvas from './components/Canvas'
import ExecutionLogs from './components/ExecutionLogs'
import NodePalette from './components/NodePalette'
import PropertiesPanel from './components/PropertiesPanel'
import type { NodeStatus, Workflow, WorkflowEdge, WorkflowGraph, WorkflowNode } from './types'
import './App.css'

const initialNodes: WorkflowNode[] = []
const initialEdges: WorkflowEdge[] = []

function App() {
  const [nodes, setNodes] = useState<WorkflowNode[]>(initialNodes)
  const [edges, setEdges] = useState<WorkflowEdge[]>(initialEdges)
  const [name, setName] = useState('New workflow')
  const [workflows, setWorkflows] = useState<Workflow[]>([])
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<number | null>(null)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [executionId, setExecutionId] = useState<number | null>(null)
  const [nodeStatuses, setNodeStatuses] = useState<Record<string, NodeStatus>>({})
  const [logs, setLogs] = useState<Record<string, string>>({})
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const selectedNode = useMemo(
    () => nodes.find((node) => node.id === selectedNodeId) ?? null,
    [nodes, selectedNodeId],
  )

  const onNodesChange = useCallback((changes: NodeChange<WorkflowNode>[]) => {
    setNodes((current) => applyNodeChanges(changes, current))
  }, [])

  const onEdgesChange = useCallback((changes: EdgeChange<WorkflowEdge>[]) => {
    setEdges((current) => applyEdgeChanges(changes, current))
  }, [])

  const toGraph = useCallback((): WorkflowGraph => ({ nodes, edges }), [nodes, edges])

  const loadWorkflows = useCallback(async () => {
    const list = await api.listWorkflows()
    setWorkflows(list)
  }, [])

  const saveWorkflow = useCallback(async () => {
    const payload = { name, version: 1, graph: toGraph() }
    if (selectedWorkflowId) {
      const workflow = await api.updateWorkflow(selectedWorkflowId, payload)
      setSelectedWorkflowId(workflow.id)
    } else {
      const workflow = await api.createWorkflow(payload)
      setSelectedWorkflowId(workflow.id)
    }
    await loadWorkflows()
  }, [name, selectedWorkflowId, toGraph, loadWorkflows])

  const loadWorkflow = useCallback(async () => {
    if (!selectedWorkflowId) return
    const workflow = await api.getWorkflow(selectedWorkflowId)
    setName(workflow.name)
    setNodes(workflow.graph.nodes)
    setEdges(workflow.graph.edges)
    setNodeStatuses({})
    setLogs({})
  }, [selectedWorkflowId])

  const runWorkflow = useCallback(async () => {
    const payload = { name, version: 1, graph: toGraph() }
    let id = selectedWorkflowId
    if (id) {
      await api.updateWorkflow(id, payload)
    } else {
      const workflow = await api.createWorkflow(payload)
      id = workflow.id
      setSelectedWorkflowId(id)
      await loadWorkflows()
    }
    if (!id) return
    const result = await api.runWorkflow(id)
    setExecutionId(result.execution_id)
    setNodeStatuses({})
    setLogs({})
  }, [loadWorkflows, name, selectedWorkflowId, toGraph])

  const exportWorkflow = useCallback(async () => {
    if (!selectedWorkflowId) return
    const workflow = await api.exportWorkflow(selectedWorkflowId)
    const blob = new Blob([JSON.stringify(workflow, null, 2)], { type: 'application/json' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `${workflow.name.replace(/\s+/g, '-')}.json`
    link.click()
    URL.revokeObjectURL(link.href)
  }, [selectedWorkflowId])

  const importWorkflow = useCallback(async (file: File) => {
    const text = await file.text()
    const payload = JSON.parse(text)
    const workflow = await api.importWorkflow(payload)
    setSelectedWorkflowId(workflow.id)
    setName(workflow.name)
    setNodes(workflow.graph.nodes)
    setEdges(workflow.graph.edges)
    await loadWorkflows()
  }, [loadWorkflows])

  const updateNodeData = useCallback((nodeId: string, data: Record<string, unknown>) => {
    setNodes((current) =>
      current.map((node) => (node.id === nodeId ? { ...node, data: { ...node.data, ...data } } : node)),
    )
  }, [])

  useExecutionSocket(
    executionId,
    useCallback((message) => {
      if (message.type === 'node' && message.node_id) {
        setNodeStatuses((current) => ({ ...current, [message.node_id!]: message.status as NodeStatus }))
        if (message.logs) {
          setLogs((current) => ({ ...current, [message.node_id!]: message.logs || '' }))
        }
      }
    }, []),
  )

  return (
    <ReactFlowProvider>
      <div className="app">
        <header className="toolbar">
          <button onClick={() => { setNodes([]); setEdges([]); setSelectedWorkflowId(null); setName('New workflow') }}>Nouveau</button>
          <button onClick={saveWorkflow}>Sauvegarder</button>
          <button onClick={loadWorkflows}>Charger liste</button>
          <select
            value={selectedWorkflowId ?? ''}
            onChange={(event) => setSelectedWorkflowId(event.target.value ? Number(event.target.value) : null)}
          >
            <option value="">Choisir un workflow</option>
            {workflows.map((workflow) => (
              <option value={workflow.id} key={workflow.id}>
                {workflow.name}
              </option>
            ))}
          </select>
          <button onClick={loadWorkflow}>Charger</button>
          <button onClick={runWorkflow}>Exécuter</button>
          <button onClick={exportWorkflow}>Exporter JSON</button>
          <button onClick={() => fileInputRef.current?.click()}>Importer JSON</button>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/json"
            style={{ display: 'none' }}
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (file) {
                void importWorkflow(file)
              }
              event.target.value = ''
            }}
          />
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Workflow name" />
        </header>

        <main className="content">
          <NodePalette />
          <Canvas
            nodes={nodes}
            edges={edges}
            nodeStatuses={nodeStatuses}
            selectedNodeId={selectedNodeId}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            setNodes={setNodes}
            setEdges={setEdges}
            onSelectNode={setSelectedNodeId}
          />
          <PropertiesPanel node={selectedNode} onChange={updateNodeData} />
        </main>

        <ExecutionLogs logs={logs} />
      </div>
    </ReactFlowProvider>
  )
}

export default App
