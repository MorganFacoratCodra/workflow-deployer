type Props = {
  logs: Record<string, string>
}

export default function ExecutionLogs({ logs }: Props) {
  return (
    <section className="logs">
      <h3>Execution logs</h3>
      {Object.keys(logs).length === 0 ? (
        <p>No logs yet</p>
      ) : (
        Object.entries(logs).map(([nodeId, nodeLogs]) => (
          <div key={nodeId} className="log-block">
            <strong>{nodeId}</strong>
            <pre>{nodeLogs}</pre>
          </div>
        ))
      )}
    </section>
  )
}
