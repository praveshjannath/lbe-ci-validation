import readline from "node:readline";
import { AgentRuntime, createAgentRuntime } from "@cline/agents";

const PROTOCOL_VERSION = "lbe-cline-stdio/1";
const PINNED_CLINE_AGENTS_VERSION = "0.0.75";
const DEFAULT_TOOL_RESULT_TIMEOUT_MS = 30_000;
const PYTHON_TO_NODE = new Set([
  "runtime.start",
  "turn.execute",
  "tool.result",
  "control.cancel",
  "control.steer",
  "runtime.shutdown",
]);

let sequence = 0;
let started = false;
let shuttingDown = false;
let allowedTools = [];
let runtime = null;
let providerSummary = null;
let activeTurn = null;
const pendingToolResults = new Map();

function write(messageType, source, payload = {}, identities = {}) {
  sequence += 1;
  const frame = {
    protocol_version: PROTOCOL_VERSION,
    message_id: `node-${sequence}`,
    message_type: messageType,
    session_id: source.session_id,
    turn_id: source.turn_id,
    payload,
  };
  for (const key of [
    "cline_tool_call_id",
    "lbe_call_id",
    "operation_id",
    "receipt_id",
  ]) {
    if (typeof identities[key] === "string" && identities[key].trim()) {
      frame[key] = identities[key];
    }
  }
  process.stdout.write(`${JSON.stringify(frame)}\n`);
}

function fail(source, code, message) {
  write("runtime.error", source, { code, message });
}

function validate(frame) {
  if (!frame || typeof frame !== "object" || Array.isArray(frame)) {
    throw new Error("frame must be an object");
  }
  for (const key of [
    "protocol_version",
    "message_id",
    "message_type",
    "session_id",
    "turn_id",
  ]) {
    if (typeof frame[key] !== "string" || !frame[key].trim()) {
      throw new Error(`${key} must be a non-empty string`);
    }
  }
  if (frame.protocol_version !== PROTOCOL_VERSION) {
    throw new Error(
      `unsupported protocol_version: ${frame.protocol_version}`,
    );
  }
  if (!PYTHON_TO_NODE.has(frame.message_type)) {
    throw new Error(
      `unknown or invalid message_type: ${frame.message_type}`,
    );
  }
  if (frame.payload !== undefined && (
    !frame.payload ||
    typeof frame.payload !== "object" ||
    Array.isArray(frame.payload)
  )) {
    throw new Error("payload must be an object");
  }
}

function safeModelToolName(toolId, index) {
  const normalized = toolId.replace(/[^A-Za-z0-9_-]/g, "_");
  return `lbe_${index}_${normalized}`;
}

function validateAllowedTools(value) {
  if (!Array.isArray(value)) {
    throw new Error("allowed_tools must be an array");
  }
  const ids = new Set();
  const modelNames = new Set();
  return value.map((tool, index) => {
    if (!tool || typeof tool !== "object" || Array.isArray(tool)) {
      throw new Error("allowed tool definition must be an object");
    }
    if (typeof tool.tool_id !== "string" || !tool.tool_id.trim()) {
      throw new Error("allowed tool tool_id must be a non-empty string");
    }
    if (ids.has(tool.tool_id)) {
      throw new Error(`duplicate allowed tool_id: ${tool.tool_id}`);
    }
    ids.add(tool.tool_id);
    const modelName = safeModelToolName(tool.tool_id, index);
    if (modelNames.has(modelName)) {
      throw new Error(`duplicate model tool name: ${modelName}`);
    }
    modelNames.add(modelName);
    const inputSchema = tool.input_schema ?? {
      type: "object",
      additionalProperties: true,
    };
    if (!inputSchema || typeof inputSchema !== "object" || Array.isArray(inputSchema)) {
      throw new Error(`input_schema must be an object for ${tool.tool_id}`);
    }
    const timeoutMs = tool.timeout_ms ?? DEFAULT_TOOL_RESULT_TIMEOUT_MS;
    if (!Number.isInteger(timeoutMs) || timeoutMs <= 0) {
      throw new Error(`timeout_ms must be a positive integer for ${tool.tool_id}`);
    }
    return {
      tool_id: tool.tool_id,
      model_name: modelName,
      description:
        typeof tool.description === "string" && tool.description.trim()
          ? tool.description
          : `LBE governed tool ${tool.tool_id}`,
      input_schema: inputSchema,
      timeout_ms: timeoutMs,
    };
  });
}

function validateProviderConfig(value) {
  if (value === undefined || value === null) {
    return null;
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("provider must be an object");
  }
  for (const key of ["provider_id", "model_id"]) {
    if (typeof value[key] !== "string" || !value[key].trim()) {
      throw new Error(`${key} must be a non-empty string`);
    }
  }
  for (const key of ["api_key", "base_url"]) {
    if (value[key] !== undefined && (
      typeof value[key] !== "string" ||
      !value[key].trim()
    )) {
      throw new Error(`${key} must be a non-empty string when present`);
    }
  }
  if (value.headers !== undefined && (
    !value.headers ||
    typeof value.headers !== "object" ||
    Array.isArray(value.headers)
  )) {
    throw new Error("provider headers must be an object when present");
  }
  if (value.options !== undefined && (
    !value.options ||
    typeof value.options !== "object" ||
    Array.isArray(value.options)
  )) {
    throw new Error("provider options must be an object when present");
  }
  return {
    provider_id: value.provider_id,
    model_id: value.model_id,
    api_key: value.api_key,
    base_url: value.base_url,
    headers: value.headers,
    options: value.options,
  };
}

function providerEventPayload(event) {
  const payload = { event_type: event.type };
  if (Number.isInteger(event.iteration)) {
    payload.iteration = event.iteration;
  }
  if (event.type === "assistant-text-delta" && typeof event.text === "string") {
    payload.text = event.text;
  }
  if (event.type === "status-notice" && typeof event.message === "string") {
    payload.message = event.message;
  }
  if (event.type === "usage-updated" && event.usage) {
    payload.usage = event.usage;
  }
  if (event.type === "turn-finished" && Number.isInteger(event.toolCallCount)) {
    payload.tool_call_count = event.toolCallCount;
  }
  return payload;
}

function makeProxyTool(definition) {
  return {
    name: definition.model_name,
    description: definition.description,
    inputSchema: definition.input_schema,
    timeoutMs: definition.timeout_ms,
    async execute(input, context) {
      if (!activeTurn) {
        throw new Error("LBE tool proxy invoked without an active turn");
      }
      const toolCallId = context?.toolCallId;
      if (typeof toolCallId !== "string" || !toolCallId.trim()) {
        throw new Error("Cline tool call is missing toolCallId");
      }
      if (pendingToolResults.has(toolCallId)) {
        throw new Error(`duplicate pending Cline tool call: ${toolCallId}`);
      }
      const operationId = `${activeTurn.turn_id}:tool:${toolCallId}`;
      const lbeCallId = `${activeTurn.turn_id}:lbe:${toolCallId}`;
      write(
        "tool.proposed",
        activeTurn,
        {
          tool_id: definition.tool_id,
          model_tool_name: definition.model_name,
          arguments: input ?? {},
        },
        {
          cline_tool_call_id: toolCallId,
          lbe_call_id: lbeCallId,
          operation_id: operationId,
        },
      );
      return await new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          pendingToolResults.delete(toolCallId);
          reject(new Error(`LBE tool result timeout: ${definition.tool_id}`));
        }, definition.timeout_ms);
        pendingToolResults.set(toolCallId, {
          resolve,
          reject,
          timer,
          source: activeTurn,
          operation_id: operationId,
          lbe_call_id: lbeCallId,
          tool_id: definition.tool_id,
        });
      });
    },
  };
}

function settleToolResult(frame) {
  const toolCallId = frame.cline_tool_call_id;
  if (typeof toolCallId !== "string" || !toolCallId.trim()) {
    throw new Error("tool.result requires cline_tool_call_id");
  }
  const pending = pendingToolResults.get(toolCallId);
  if (!pending) {
    throw new Error(`unknown or duplicate cline_tool_call_id: ${toolCallId}`);
  }
  if (
    frame.session_id !== pending.source.session_id ||
    frame.turn_id !== pending.source.turn_id
  ) {
    throw new Error("tool.result session/turn identity mismatch");
  }
  if (frame.operation_id !== pending.operation_id) {
    throw new Error("tool.result operation_id mismatch");
  }
  if (frame.lbe_call_id !== pending.lbe_call_id) {
    throw new Error("tool.result lbe_call_id mismatch");
  }
  clearTimeout(pending.timer);
  pendingToolResults.delete(toolCallId);
  const status = frame.payload?.status;
  if (status === "EXECUTED") {
    pending.resolve(frame.payload?.output ?? {});
    return;
  }
  const code = frame.payload?.error_code ?? status ?? "LBE_TOOL_FAILED";
  const message = frame.payload?.error_message ?? "LBE governed tool did not execute";
  pending.reject(new Error(`${code}: ${message}`));
}

function rejectPendingToolResults(reason) {
  for (const [toolCallId, pending] of pendingToolResults.entries()) {
    clearTimeout(pending.timer);
    pending.reject(new Error(reason));
    pendingToolResults.delete(toolCallId);
  }
}

function buildRuntime(frame, provider) {
  if (!provider) {
    return null;
  }
  const payload = frame.payload ?? {};
  const maxIterations = payload.max_iterations ?? 8;
  if (!Number.isInteger(maxIterations) || maxIterations <= 0) {
    throw new Error("max_iterations must be a positive integer");
  }
  const instance = createAgentRuntime({
    providerId: provider.provider_id,
    modelId: provider.model_id,
    apiKey: provider.api_key,
    baseUrl: provider.base_url,
    headers: provider.headers,
    options: provider.options,
    sessionId: frame.session_id,
    conversationId:
      typeof payload.conversation_id === "string" && payload.conversation_id.trim()
        ? payload.conversation_id
        : frame.session_id,
    systemPrompt:
      typeof payload.system_prompt === "string" ? payload.system_prompt : undefined,
    maxIterations,
    tools: allowedTools.map(makeProxyTool),
  });
  instance.subscribe((event) => {
    if (activeTurn && !shuttingDown) {
      write("provider.event", activeTurn, providerEventPayload(event));
    }
  });
  return instance;
}

async function executeTurn(frame) {
  if (!runtime) {
    write("turn.failed", frame, {
      code: "PROVIDER_RUNTIME_NOT_CONFIGURED",
      message: "runtime.start must include provider configuration before turn.execute",
    });
    return;
  }
  if (activeTurn) {
    write("turn.failed", frame, {
      code: "TURN_ALREADY_RUNNING",
      message: "only one Cline AgentRuntime turn may run at a time",
    });
    return;
  }
  const text = frame.payload?.text;
  if (typeof text !== "string" || !text.trim()) {
    write("turn.failed", frame, {
      code: "INVALID_TURN_INPUT",
      message: "turn.execute payload.text must be a non-empty string",
    });
    return;
  }
  activeTurn = frame;
  try {
    const result = await runtime.run(text);
    if (!shuttingDown) {
      if (result.status === "failed") {
        write("turn.failed", frame, {
          code: "CLINE_AGENTRUNTIME_FAILED",
          message: String(result.error?.message ?? "Cline AgentRuntime failed"),
          status: result.status,
          run_id: result.runId,
          iterations: result.iterations,
          output_text: result.outputText,
          usage: result.usage,
          lbe_completion_truth: false,
        });
      } else {
        write("turn.completed", frame, {
          status: result.status,
          run_id: result.runId,
          iterations: result.iterations,
          output_text: result.outputText,
          usage: result.usage,
          lbe_completion_truth: false,
        });
      }
    }
  } catch (error) {
    if (!shuttingDown) {
      write("turn.failed", frame, {
        code: "CLINE_AGENTRUNTIME_FAILED",
        message: String(error?.message ?? error),
      });
    }
  } finally {
    rejectPendingToolResults("Cline turn ended before LBE tool result completed");
    activeTurn = null;
  }
}

const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });

rl.on("line", (line) => {
  let frame;
  try {
    frame = JSON.parse(line);
    validate(frame);
  } catch (error) {
    fail(
      frame ?? { session_id: "unknown", turn_id: "unknown" },
      "PROTOCOL_ERROR",
      String(error?.message ?? error),
    );
    process.exitCode = 2;
    rl.close();
    return;
  }

  if (frame.message_type === "runtime.start") {
    if (started) {
      fail(frame, "DUPLICATE_START", "runtime already started");
      process.exitCode = 2;
      rl.close();
      return;
    }
    try {
      allowedTools = validateAllowedTools(frame.payload?.allowed_tools ?? []);
      const provider = validateProviderConfig(frame.payload?.provider);
      runtime = buildRuntime(frame, provider);
      providerSummary = provider
        ? { provider_id: provider.provider_id, model_id: provider.model_id }
        : null;
    } catch (error) {
      fail(frame, "INVALID_RUNTIME_CONFIG", String(error?.message ?? error));
      process.exitCode = 2;
      rl.close();
      return;
    }
    started = true;
    write("runtime.ready", frame, {
      worker_version: "0.2.0",
      cline_agents_version: PINNED_CLINE_AGENTS_VERSION,
      agent_runtime_export: typeof AgentRuntime === "function",
      create_agent_runtime_export: typeof createAgentRuntime === "function",
      provider_configured: runtime !== null,
      provider: providerSummary,
      allowed_tool_ids: allowedTools.map((tool) => tool.tool_id),
      allowed_tools: allowedTools.map((tool) => ({
        tool_id: tool.tool_id,
        model_name: tool.model_name,
      })),
      native_mutation_tools_registered: false,
    });
    return;
  }

  if (!started) {
    fail(frame, "RUNTIME_NOT_STARTED", "runtime.start required first");
    process.exitCode = 2;
    rl.close();
    return;
  }

  if (frame.message_type === "runtime.shutdown") {
    shuttingDown = true;
    runtime?.abort("LBE runtime shutdown");
    rejectPendingToolResults("LBE runtime shutdown");
    write("turn.completed", frame, { shutdown: true });
    rl.close();
    return;
  }

  if (frame.message_type === "turn.execute") {
    void executeTurn(frame);
    return;
  }

  if (frame.message_type === "tool.result") {
    try {
      settleToolResult(frame);
    } catch (error) {
      fail(frame, "TOOL_RESULT_IDENTITY_ERROR", String(error?.message ?? error));
      runtime?.abort(error);
      process.exitCode = 2;
      rl.close();
    }
    return;
  }

  if (frame.message_type === "control.cancel") {
    if (!activeTurn || !runtime) {
      fail(frame, "NO_ACTIVE_TURN", "control.cancel requires an active turn");
      return;
    }
    runtime.abort(frame.payload?.reason ?? "Cancelled by LBE");
    return;
  }

  if (frame.message_type === "control.steer") {
    fail(
      frame,
      "STEERING_UNSUPPORTED",
      "control.steer is intentionally not enabled in this bounded slice",
    );
  }
});

rl.on("close", () => {
  if (process.exitCode === undefined) {
    process.exitCode = 0;
  }
});