import type { NodeProps } from '@xyflow/react'
import { Handle, Position } from '@xyflow/react'

const colors: Record<string, string> = {
  pending: '#9ca3af',
  running: '#3b82f6',
  success: '#16a34a',
  failed: '#dc2626',
  skipped: '#eab308',
}

export default function StatusNode({ data }: NodeProps) {
  const nodeData = (data ?? {}) as { label?: string; status?: string }
  const color = colors[nodeData.status || 'pending'] || colors.pending
  return (
    <div
      style={{
        border: `2px solid ${color}`,
        borderRadius: 8,
        background: '#fff',
        padding: '8px 10px',
        minWidth: 120,
      }}
    >
      <Handle type="target" position={Position.Left} />
      <div style={{ fontWeight: 600 }}>{nodeData.label || 'Node'}</div>
      <small style={{ color }}>{nodeData.status || 'pending'}</small>
      <Handle type="source" position={Position.Right} />
    </div>
  )
}
