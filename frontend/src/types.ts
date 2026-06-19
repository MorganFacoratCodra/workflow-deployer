import type { Edge, Node } from '@xyflow/react'

export type NodeStatus = 'pending' | 'running' | 'success' | 'failed' | 'skipped'

export type WorkflowNodeData = {
  label: string
  command?: string
  repoPath?: string
  addAll?: boolean
  commit?: boolean
  push?: boolean
  remote?: string
  branch?: string
  method?: string
  url?: string
  body?: string
  expression?: string
  message?: string
  seconds?: number
  host?: string
  port?: number
  username?: string
  password?: string
  privateKey?: string
  passphrase?: string
  timeout?: number
}

export type WorkflowNode = Node<WorkflowNodeData>
export type WorkflowEdge = Edge & { on?: 'success' | 'failure' }

export type WorkflowGraph = {
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
}

export type Workflow = {
  id: number
  name: string
  version: number
  graph: WorkflowGraph
  created_at: string
  updated_at: string
}

export type Execution = {
  id: number
  workflow_id: number
  status: NodeStatus | 'pending'
  started_at: string
  finished_at: string | null
}

export type NodeRun = {
  id: number
  execution_id: number
  node_id: string
  status: NodeStatus
  logs: string
  duration_ms: number | null
}
