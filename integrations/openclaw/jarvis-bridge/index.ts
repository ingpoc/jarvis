import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import { setTimeout as sleep } from "node:timers/promises";

import type { AnyAgentTool, OpenClawPluginApi } from "openclaw/plugin-sdk";

type PluginCfg = {
  baseUrl?: string;
  tokenPath?: string;
  tokenEnv?: string;
  token?: string;
  defaultWait?: boolean;
  defaultTimeoutSec?: number;
  pollIntervalMs?: number;
};

type JsonObject = Record<string, unknown>;
type JobEntry = {
  contextId: string;
  lastTaskId: string;
  updatedAt: number;
  lastStatus?: string;
  opencodeSessionId?: string;
};

type ScopeState = {
  jobs: Record<string, JobEntry>;
  lastJobId?: string;
};

type BridgeState = {
  version: 1;
  scopes: Record<string, ScopeState>;
};

const TERMINAL_STATES = new Set(["completed", "failed", "canceled", "rejected"]);

const JarvisTaskSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    task: { type: "string", description: "Task to delegate to Jarvis." },
    command: {
      type: "string",
      description: "Raw command payload from skill command-dispatch mode (used as task when provided).",
    },
    taskType: {
      type: "string",
      enum: ["coding", "research", "analysis", "ops", "general"],
      description: "Optional task classification for logging/routing.",
    },
    commandName: { type: "string" },
    skillName: { type: "string" },
    jobId: { type: "string", description: "Stable logical job id for follow-up routing." },
    followUp: {
      type: "boolean",
      description: "Resume the most recent job in the current scope when jobId/contextId are omitted.",
    },
    contextId: { type: "string", description: "Optional A2A context id." },
    resumeSessionId: { type: "string", description: "Optional OpenCode session id to resume explicitly." },
    wait: { type: "boolean", description: "Wait for completion before returning." },
    timeoutSec: {
      type: "number",
      minimum: 5,
      maximum: 18000,
      description: "Max wait duration when wait=true.",
    },
    pollIntervalMs: {
      type: "number",
      minimum: 100,
      maximum: 10000,
      description: "Polling interval when wait=true.",
    },
    researchHandoff: {
      type: "object",
      additionalProperties: false,
      description: "Optional structured research verdict handoff for Jarvis gating.",
      properties: {
        researchId: { type: "string" },
        proposedVerdict: { type: "string", enum: ["adopt", "adapt", "skip"] },
        confidence: { type: "number", minimum: 0, maximum: 1 },
        mustUseInWorkflow: { type: "boolean" },
        notes: { type: "string" },
      },
      required: ["researchId", "proposedVerdict"],
    },
  },
} as const;

function jsonText(payload: unknown) {
  return JSON.stringify(payload, null, 2);
}

function expandHome(rawPath: string): string {
  if (!rawPath.startsWith("~")) {
    return rawPath;
  }
  const home = process.env.HOME || "";
  if (!home) {
    return rawPath;
  }
  return path.join(home, rawPath.slice(1));
}

async function resolveToken(cfg: PluginCfg): Promise<string> {
  if (cfg.token && cfg.token.trim()) {
    return cfg.token.trim();
  }

  const tokenEnvKey = (cfg.tokenEnv || "JARVIS_A2A_TOKEN").trim();
  if (tokenEnvKey) {
    const envToken = process.env[tokenEnvKey];
    if (envToken && envToken.trim()) {
      return envToken.trim();
    }
  }

  const tokenPath = expandHome(cfg.tokenPath || "~/.jarvis/system/jarvis_config/a2a_token");
  try {
    const token = (await fs.readFile(tokenPath, "utf8")).trim();
    if (token) {
      return token;
    }
  } catch {
    // Handled below with explicit error.
  }

  throw new Error(
    `Missing Jarvis A2A token. Provide plugins.entries.jarvis-bridge.config.token, ` +
      `${tokenEnvKey}, or tokenPath (${tokenPath}).`,
  );
}

function resolveBaseUrl(cfg: PluginCfg): string {
  const raw = (cfg.baseUrl || process.env.JARVIS_A2A_URL || "http://127.0.0.1:9848").trim();
  return raw.replace(/\/+$/, "");
}

function stateFilePath(): string {
  return path.join(os.homedir(), ".openclaw", "jarvis-bridge-jobs.json");
}

function buildScopeKey(rawScopeKey?: string): string {
  const value = String(rawScopeKey || "").trim();
  return value || "global";
}

async function loadBridgeState(): Promise<BridgeState> {
  const file = stateFilePath();
  try {
    const raw = await fs.readFile(file, "utf8");
    const parsed = JSON.parse(raw) as Partial<BridgeState>;
    const scopes = parsed.scopes && typeof parsed.scopes === "object" ? parsed.scopes : {};
    return {
      version: 1,
      scopes: scopes as Record<string, ScopeState>,
    };
  } catch {
    return { version: 1, scopes: {} };
  }
}

async function saveBridgeState(state: BridgeState): Promise<void> {
  const file = stateFilePath();
  await fs.mkdir(path.dirname(file), { recursive: true });
  await fs.writeFile(file, JSON.stringify(state, null, 2), "utf8");
}

function getScopeState(state: BridgeState, scopeKey: string): ScopeState {
  const existing = state.scopes[scopeKey];
  if (existing && typeof existing === "object" && existing.jobs && typeof existing.jobs === "object") {
    return existing;
  }
  const created: ScopeState = { jobs: {} };
  state.scopes[scopeKey] = created;
  return created;
}

async function postJson(
  url: string,
  body: JsonObject,
  token: string,
  timeoutMs: number,
): Promise<JsonObject> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });
    const text = await res.text();
    let parsed: unknown = {};
    if (text.trim()) {
      parsed = JSON.parse(text);
    }
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${typeof parsed === "string" ? parsed : text}`);
    }
    if (!parsed || typeof parsed !== "object") {
      throw new Error(`Unexpected response from Jarvis A2A: ${text}`);
    }
    return parsed as JsonObject;
  } finally {
    clearTimeout(timer);
  }
}

async function a2aCall(
  baseUrl: string,
  token: string,
  method: string,
  params: JsonObject,
  timeoutMs: number,
): Promise<JsonObject> {
  const payload = {
    jsonrpc: "2.0",
    id: `jarvis-bridge-${Date.now()}`,
    method,
    params,
  };
  const response = await postJson(`${baseUrl}/`, payload, token, timeoutMs);
  if (response.error) {
    const err = response.error as JsonObject;
    const code = err.code ?? "unknown";
    const msg = err.message ?? "Unknown JSON-RPC error";
    throw new Error(`${method} failed (code=${String(code)}): ${String(msg)}`);
  }
  const result = response.result;
  if (!result || typeof result !== "object") {
    throw new Error(`${method} returned invalid response.`);
  }
  return result as JsonObject;
}

function toResult(payload: JsonObject, statusText?: string) {
  const prefix = statusText ? `${statusText}\n\n` : "";
  return {
    content: [{ type: "text", text: `${prefix}${jsonText(payload)}` }],
    details: payload,
  };
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function normalizeGatewayPayload(payload: unknown): Record<string, unknown> {
  const root = asRecord(payload);
  if (!root) {
    return {};
  }

  if (typeof root.task === "string" || typeof root.command === "string") {
    return root;
  }

  const directParams = asRecord(root.params);
  if (directParams && (typeof directParams.task === "string" || typeof directParams.command === "string")) {
    return directParams;
  }

  const nestedPayload = asRecord(root.payload);
  if (nestedPayload && (typeof nestedPayload.task === "string" || typeof nestedPayload.command === "string")) {
    return nestedPayload;
  }

  const args = asRecord(root.args);
  if (args && (typeof args.task === "string" || typeof args.command === "string")) {
    return args;
  }

  return root;
}

type ResearchHandoff = {
  researchId: string;
  proposedVerdict: "adopt" | "adapt" | "skip";
  confidence?: number;
  mustUseInWorkflow?: boolean;
  notes?: string;
};

function normalizeResearchHandoff(params: Record<string, unknown>): ResearchHandoff | null {
  const raw = asRecord(params.researchHandoff) ?? asRecord(params.research_handoff);
  if (!raw) {
    return null;
  }
  const researchId = String(raw.researchId || "").trim();
  const proposedVerdict = String(raw.proposedVerdict || "").trim().toLowerCase();
  if (!researchId || !["adopt", "adapt", "skip"].includes(proposedVerdict)) {
    return null;
  }

  const handoff: ResearchHandoff = {
    researchId,
    proposedVerdict: proposedVerdict as ResearchHandoff["proposedVerdict"],
  };

  if (typeof raw.confidence === "number" && Number.isFinite(raw.confidence)) {
    handoff.confidence = Math.max(0, Math.min(1, raw.confidence));
  }
  if (typeof raw.mustUseInWorkflow === "boolean") {
    handoff.mustUseInWorkflow = raw.mustUseInWorkflow;
  }
  if (typeof raw.notes === "string" && raw.notes.trim()) {
    handoff.notes = raw.notes.trim();
  }
  return handoff;
}

async function executeJarvisCodeTask(
  api: OpenClawPluginApi,
  _toolCallId: string,
  params: Record<string, unknown>,
  opts?: { scopeKey?: string },
): Promise<{ content: Array<{ type: string; text: string }>; details?: unknown }> {
  const cfg = (api.pluginConfig || {}) as PluginCfg;
  const task = String(params.task ?? params.command ?? "").trim();
  if (!task) {
    return toResult({ error: "Missing task. Provide `task` or command args." });
  }
  const researchHandoff = normalizeResearchHandoff(params);

  const wait = Boolean(params.wait ?? cfg.defaultWait ?? false);
  const timeoutSec = Number(params.timeoutSec ?? cfg.defaultTimeoutSec ?? 300);
  const pollIntervalMs = Number(params.pollIntervalMs ?? cfg.pollIntervalMs ?? 1000);
  const scopeKey = buildScopeKey(opts?.scopeKey);
  const state = await loadBridgeState();
  const scope = getScopeState(state, scopeKey);
  const requestedJobId = typeof params.jobId === "string" ? params.jobId.trim() : "";
  const requestedContextId = typeof params.contextId === "string" ? params.contextId.trim() : "";
  const requestedResumeSessionId =
    typeof params.resumeSessionId === "string" ? params.resumeSessionId.trim() : "";
  const followUp = Boolean(params.followUp ?? false);

  let jobId = requestedJobId;
  let contextId = requestedContextId;
  let resumeSessionId = requestedResumeSessionId;
  let resumeSource = "explicit";

  if (!contextId && jobId && scope.jobs[jobId]?.contextId) {
    contextId = scope.jobs[jobId].contextId;
    if (!resumeSessionId && scope.jobs[jobId]?.opencodeSessionId) {
      resumeSessionId = scope.jobs[jobId].opencodeSessionId || "";
    }
    resumeSource = "job";
  }
  if (!contextId && !jobId && followUp && scope.lastJobId && scope.jobs[scope.lastJobId]?.contextId) {
    jobId = scope.lastJobId;
    contextId = scope.jobs[jobId].contextId;
    if (!resumeSessionId && scope.jobs[jobId]?.opencodeSessionId) {
      resumeSessionId = scope.jobs[jobId].opencodeSessionId || "";
    }
    resumeSource = "latest";
  }
  if (!jobId) {
    jobId = `job-${crypto.randomUUID().slice(0, 8)}`;
    resumeSource = "new";
  }
  if (!contextId) {
    contextId = `ctx-${jobId}`;
  }

  const baseUrl = resolveBaseUrl(cfg);
  const token = await resolveToken(cfg);

  const delegatedMessage = researchHandoff
    ? `${task}\n\n[RESEARCH_HANDOFF_JSON]\n${JSON.stringify(researchHandoff)}\n[/RESEARCH_HANDOFF_JSON]`
    : task;
  const sendParams: JsonObject = {
    message: delegatedMessage,
    blocking: false,
    contextId,
  };
  if (resumeSessionId) {
    sendParams.resumeSessionId = resumeSessionId;
  }
  const submitted = await a2aCall(
    baseUrl,
    token,
    "message/send",
    sendParams,
    15000,
  );

  const taskId = String(submitted.taskId || "");
  if (!taskId) {
    return toResult({ submitted, error: "Jarvis did not return a taskId." });
  }

  const existingEntry = scope.jobs[jobId];
  scope.jobs[jobId] = {
    ...(existingEntry || { contextId }),
    contextId,
    lastTaskId: taskId,
    updatedAt: Date.now(),
    lastStatus: String(submitted.status || "submitted"),
    opencodeSessionId: existingEntry?.opencodeSessionId,
  };
  scope.lastJobId = jobId;
  await saveBridgeState(state);

  if (!wait) {
    return toResult(
      {
        submitted,
          bridge: {
            mode: "non-blocking",
            scopeKey,
            jobId,
            contextId,
            resumeSessionId: resumeSessionId || undefined,
            resumeSource,
            getTask: "Use jobId/contextId for follow-ups to keep the same Jarvis/OpenCode context.",
            researchHandoff: researchHandoff || undefined,
          },
      },
      "Delegated to Jarvis (non-blocking).",
    );
  }

  const deadline = Date.now() + timeoutSec * 1000;
  let last: JsonObject = { taskId, status: submitted.status ?? "submitted" };

  while (Date.now() < deadline) {
    last = await a2aCall(baseUrl, token, "tasks/get", { taskId }, 15000);
    const status = String(last.status || "").toLowerCase().trim();
    if (TERMINAL_STATES.has(status)) {
      const artifacts = Array.isArray(last.artifacts) ? (last.artifacts as Array<Record<string, unknown>>) : [];
      const opencodeSessionArtifact = artifacts.find((a) => String(a?.name || "") === "opencode_session");
      const opencodeSessionId = String(opencodeSessionArtifact?.content || "").trim();
      scope.jobs[jobId] = {
        ...(scope.jobs[jobId] || { contextId }),
        contextId,
        lastTaskId: taskId,
        updatedAt: Date.now(),
        lastStatus: status,
        opencodeSessionId: opencodeSessionId || scope.jobs[jobId]?.opencodeSessionId,
      };
      scope.lastJobId = jobId;
      await saveBridgeState(state);
      return toResult(
        {
          submitted,
          final: last,
          bridge: {
            delegatedTo: "jarvis-a2a",
            baseUrl,
            scopeKey,
            jobId,
            contextId,
            resumeSessionId: resumeSessionId || undefined,
            resumeSource,
            opencodeSessionId,
            researchHandoff: researchHandoff || undefined,
          },
        },
        `Delegated to Jarvis and completed with status: ${status}.`,
      );
    }
    await sleep(Math.max(100, pollIntervalMs));
  }

  return toResult(
    {
      submitted,
      final: last,
      bridge: {
        timeoutSec,
        pollIntervalMs,
        scopeKey,
        jobId,
        contextId,
        resumeSessionId: resumeSessionId || undefined,
        resumeSource,
      },
    },
    `Delegated to Jarvis, but timed out after ${timeoutSec}s.`,
  );
}

export default function register(api: OpenClawPluginApi) {
  // Backward-compatible legacy tool name.
  api.registerTool({
    name: "jarvis_code_task",
    label: "Jarvis Code Task",
    description:
      "Delegate coding/build/refactor/debug tasks to Jarvis over A2A JSON-RPC and return the result. (Legacy alias; prefer jarvis_delegate_task.)",
    parameters: JarvisTaskSchema,
    execute: (toolCallId: string, params: Record<string, unknown>) =>
      executeJarvisCodeTask(api, toolCallId, params),
  } as AnyAgentTool);

  api.registerTool({
    name: "jarvis_delegate_task",
    label: "Jarvis Delegate Task",
    description:
      "Delegate an execution task (coding/research/analysis/ops) to Jarvis over A2A JSON-RPC and return the result.",
    parameters: JarvisTaskSchema,
    execute: (toolCallId: string, params: Record<string, unknown>) =>
      executeJarvisCodeTask(api, toolCallId, params),
  } as AnyAgentTool);

  api.registerGatewayMethod("jarvis.codeTask", async ({ params, respond, context }) => {
    try {
      const requestParams = normalizeGatewayPayload(params);
      const scopeKey =
        String((context as Record<string, unknown> | undefined)?.sessionKey || "").trim() ||
        String((requestParams as Record<string, unknown>).sessionKey || "").trim() ||
        undefined;
      const result = await executeJarvisCodeTask(api, "gateway", requestParams, { scopeKey });
      respond(true, result.details ?? {});
    } catch (err) {
      respond(false, {
        error: err instanceof Error ? err.message : String(err),
      });
    }
  });

  api.registerGatewayMethod("jarvis.delegateTask", async ({ params, respond, context }) => {
    try {
      const requestParams = normalizeGatewayPayload(params);
      const scopeKey =
        String((context as Record<string, unknown> | undefined)?.sessionKey || "").trim() ||
        String((requestParams as Record<string, unknown>).sessionKey || "").trim() ||
        undefined;
      const result = await executeJarvisCodeTask(api, "gateway", requestParams, { scopeKey });
      respond(true, result.details ?? {});
    } catch (err) {
      respond(false, {
        error: err instanceof Error ? err.message : String(err),
      });
    }
  });

  api.registerCommand({
    name: "jarvis",
    description: "Delegate a task to Jarvis (example: /jarvis refactor auth module)",
    acceptsArgs: true,
    handler: async (ctx) => {
      const args = (ctx.args || "").trim();
      if (!args) {
        return {
          text: "Usage: /jarvis <task> (follow-up: include jobId/contextId from prior response)",
        };
      }
      try {
        const scopeKey = String((ctx as Record<string, unknown> | undefined)?.sessionKey || "").trim() || undefined;
        const result = await executeJarvisCodeTask(api, "command", { task: args, wait: true }, { scopeKey });
        return { text: result.content[0]?.text || "Delegated to Jarvis." };
      } catch (err) {
        return { text: `Jarvis delegation failed: ${err instanceof Error ? err.message : String(err)}` };
      }
    },
  });
}
