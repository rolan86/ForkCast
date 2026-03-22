/**
 * SSE connection utility for named EventSource events.
 *
 * Backend sends `event: <stage_name>` (named events).
 * Native EventSource.onmessage only fires for UNNAMED events.
 * We must use addEventListener for each stage name.
 */

const GRAPH_STAGES = [
  'extracting_text', 'chunking', 'generating_ontology',
  'extracting_entities', 'deduplicating', 'building_graph',
  'indexing', 'registering',
]

const PREPARE_STAGES = ['loading_graph', 'generating_profiles', 'generating_config', 'result']

const RUN_STAGES = ['loading', 'running', 'action', 'round', 'result']

export const SSE_STAGES = { GRAPH_STAGES, PREPARE_STAGES, RUN_STAGES }

/**
 * Connect to an SSE endpoint with named event support and auto-reconnection.
 *
 * @param {string} url - SSE endpoint URL
 * @param {string[]} stageNames - Named events to listen for
 * @param {Object} handlers - { onMessage(data), onError(message), onComplete(), onDisconnect() }
 * @returns {{ source: EventSource, close: Function }}
 */
export function connectSSE(url, stageNames, handlers) {
  let retries = 0
  const MAX_RETRIES = 3
  const RETRY_DELAY = 3000
  let source = null
  let closed = false

  function connect() {
    source = new EventSource(url)

    for (const stage of stageNames) {
      source.addEventListener(stage, (event) => {
        retries = 0 // Reset on successful message
        const data = JSON.parse(event.data)
        handlers.onMessage?.(data)
      })
    }

    source.addEventListener('error', (event) => {
      try {
        const data = JSON.parse(event.data)
        handlers.onError?.(data.message || 'Unknown error')
      } catch {
        // Not a backend error event — connection-level issue handled by onerror
      }
    })

    source.addEventListener('complete', () => {
      source.close()
      handlers.onComplete?.()
    })

    source.onerror = () => {
      if (closed) return
      source.close()
      handlers.onDisconnect?.()
      if (retries < MAX_RETRIES) {
        retries++
        setTimeout(() => {
          if (!closed) connect()
        }, RETRY_DELAY)
      }
    }
  }

  connect()

  return {
    get source() { return source },
    close() {
      closed = true
      source?.close()
    },
  }
}
