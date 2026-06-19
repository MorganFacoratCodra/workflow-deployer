import type { WorkflowNode } from '../types'

type Props = {
  node: WorkflowNode | null
  onChange: (nodeId: string, data: Record<string, unknown>) => void
}

function textField(
  node: WorkflowNode,
  key: string,
  label: string,
  onChange: (nodeId: string, data: Record<string, unknown>) => void,
  type: 'text' | 'password' | 'number' = 'text',
) {
  const value = (node.data as Record<string, unknown>)[key]
  return (
    <label className="prop-field" key={key}>
      {label}
      <input
        type={type}
        value={String(value ?? '')}
        onChange={(event) =>
          onChange(node.id, {
            [key]:
              type === 'number' ? Number.parseInt(event.target.value || '0', 10) || 0 : event.target.value,
          })
        }
      />
    </label>
  )
}

function checkboxField(
  node: WorkflowNode,
  key: string,
  label: string,
  onChange: (nodeId: string, data: Record<string, unknown>) => void,
) {
  const value = Boolean((node.data as Record<string, unknown>)[key])
  return (
    <label className="prop-checkbox" key={key}>
      <input type="checkbox" checked={value} onChange={(event) => onChange(node.id, { [key]: event.target.checked })} />
      {label}
    </label>
  )
}

function textareaField(
  node: WorkflowNode,
  key: string,
  label: string,
  onChange: (nodeId: string, data: Record<string, unknown>) => void,
) {
  const value = (node.data as Record<string, unknown>)[key]
  return (
    <label className="prop-field" key={key}>
      {label}
      <textarea value={String(value ?? '')} onChange={(event) => onChange(node.id, { [key]: event.target.value })} rows={4} />
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

  const typeKey = node.type ?? ''
  const gitCommitEnabled = Boolean((node.data as Record<string, unknown>).commit ?? true)
  const localSecretsWarning = (
    <p className="security-warning">
      ⚠️ Ces données sont stockées en clair dans le workflow JSON (usage local uniquement).
    </p>
  )

  return (
    <aside className="panel">
      <h3>{node.data.label}</h3>
      {textField(node, 'label', 'Label', onChange)}

      {typeKey === 'shell' ? textField(node, 'command', 'Command', onChange) : null}

      {typeKey === 'httpRequest' ? (
        <>
          {textField(node, 'method', 'Method', onChange)}
          {textField(node, 'url', 'URL', onChange)}
          {textareaField(node, 'body', 'Body (JSON string)', onChange)}
        </>
      ) : null}

      {typeKey === 'condition' ? textField(node, 'expression', 'Expression', onChange) : null}
      {typeKey === 'notify' ? textareaField(node, 'message', 'Message', onChange) : null}
      {typeKey === 'delay' ? textField(node, 'seconds', 'Seconds', onChange, 'number') : null}

      {typeKey === 'gitCommit' ? (
        <>
          {textField(node, 'repoPath', 'Repository path', onChange)}
          {textField(node, 'message', 'Commit message', onChange)}
          {checkboxField(node, 'addAll', 'git add -A', onChange)}
          {checkboxField(node, 'commit', 'Create commit', onChange)}
          {checkboxField(node, 'push', 'Push after commit', onChange)}
          {textField(node, 'remote', 'Remote', onChange)}
          <label className="prop-field">
            Branch
            <input
              value={String((node.data as Record<string, unknown>).branch ?? '')}
              onChange={(event) => onChange(node.id, { branch: event.target.value })}
              placeholder="Current branch if empty"
            />
          </label>
          {!gitCommitEnabled ? (
            <p className="security-warning">Le commit est désactivé, le message sera ignoré.</p>
          ) : null}
        </>
      ) : null}

      {typeKey === 'sshCommand' ? (
        <>
          {textField(node, 'host', 'Host', onChange)}
          {textField(node, 'port', 'Port', onChange, 'number')}
          {textField(node, 'username', 'Username', onChange)}
          {textField(node, 'command', 'Command', onChange)}
          {localSecretsWarning}
          {textField(node, 'password', 'Password', onChange, 'password')}
          {textareaField(node, 'privateKey', 'Private key (content or file path)', onChange)}
          {textField(node, 'passphrase', 'Key passphrase', onChange, 'password')}
          {textField(node, 'timeout', 'Timeout (seconds)', onChange, 'number')}
        </>
      ) : null}
    </aside>
  )
}
