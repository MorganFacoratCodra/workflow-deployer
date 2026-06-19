import type { DragEvent } from 'react'

const nodeTypes = [
  { type: 'manualTrigger', label: 'Manual Trigger' },
  { type: 'shell', label: 'Shell' },
  { type: 'gitCommit', label: 'Git Commit' },
  { type: 'sshCommand', label: 'SSH Command' },
  { type: 'httpRequest', label: 'HTTP Request' },
  { type: 'condition', label: 'Condition' },
  { type: 'notify', label: 'Notify' },
  { type: 'delay', label: 'Delay' },
]

export default function NodePalette() {
  const onDragStart = (event: DragEvent<HTMLDivElement>, type: string) => {
    event.dataTransfer.setData('application/reactflow', type)
    event.dataTransfer.effectAllowed = 'move'
  }

  return (
    <aside className="panel">
      <h3>Nodes</h3>
      {nodeTypes.map((nodeType) => (
        <div
          key={nodeType.type}
          className="palette-item"
          draggable
          onDragStart={(event) => onDragStart(event, nodeType.type)}
        >
          {nodeType.label}
        </div>
      ))}
    </aside>
  )
}
