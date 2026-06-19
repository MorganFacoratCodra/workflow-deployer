import type { WorkflowNode } from '../types'

type Props = {
  node: WorkflowNode | null
  onChange: (nodeId: string, data: Record<string, unknown>) => void
}

function field(
  node: WorkflowNode,
  key: string,
  label: string,
  onChange: (nodeId: string, data: Record<string, unknown>) => void,
) {
  return (
    <label className="prop-field" key={key}>
      {label}
      <input
        value={String((node.data as Record<string, unknown>)[key] ?? '')}
        onChange={(event) => onChange(node.id, { [key]: event.target.value })}
      />
    </label>
  )
}

export default function PropertiesPanel({ node, onChange }: Props) {
  if (!node) {
    return (
      <aside className="panel">
        <h3>Properties</h3>
        <p>Select a node</p>
      </aside>
    )
  }

  const fieldsByType: Record<string, Array<[string, string]>> = {
    shell: [['command', 'Command']],
    httpRequest: [
      ['method', 'Method'],
      ['url', 'URL'],
      ['body', 'Body (JSON string)'],
    ],
    condition: [['expression', 'Expression']],
    notify: [['message', 'Message']],
    delay: [['seconds', 'Seconds']],
  }
  const typeKey = node.type ?? ''

  return (
    <aside className="panel">
      <h3>{node.data.label}</h3>
      {field(node, 'label', 'Label', onChange)}
      {(fieldsByType[typeKey] ?? []).map(([key, label]: [string, string]) =>
        field(node, key, label, onChange),
      )}
    </aside>
  )
}
