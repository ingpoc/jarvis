import fs from "node:fs/promises";
import path from "node:path";
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
    contextId: { type: "string", description: "Optional A2A context id." },
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

  const tokenPath = expandHome(cfg.tokenPath || "~/.jarvis/a2a_token");
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

async function executeJarvisCodeTask(
  api: OpenClawPluginApi,
  _toolCallId: string,
  params: Record<string, unknown>,
): Promise<{ content: Array<{ type: string; text: string }>; details?: unknown }> {
  const cfg = (api.pluginConfig || {}) as PluginCfg;
  const task = String(params.task ?? params.command ?? "").trim();
  if (!task) {
    return toResult({ error: "Missing task. Provide `task` or command args." });
  }

  const wait = Boolean(params.wait ?? cfg.defaultWait ?? false);
  const timeoutSec = Number(params.timeoutSec ?? cfg.defaultTimeoutSec ?? 300);
  const pollIntervalMs = Number(params.pollIntervalMs ?? cfg.pollIntervalMs ?? 1000);
  const contextId = typeof params.contextId === "string" ? params.contextId : undefined;

  const baseUrl = resolveBaseUrl(cfg);
  const token = await resolveToken(cfg);

  const submitted = await a2aCall(
    baseUrl,
    token,
    "message/send",
    {
      message: task,
      blocking: false,
      ...(contextId ? { contextId } : {}),
    },
    15000,
  );

  const taskId = String(submitted.taskId || "");
  if (!taskId) {
    return toResult({ submitted, error: "Jarvis did not return a taskId." });
  }

  if (!wait) {
    return toResult(
      {
        submitted,
        bridge: {
          mode: "non-blocking",
          getTask: "Use tool `jarvis_delegate_task` with the same task id via `contextId` for follow-up if needed.",
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
      return toResult(
        {
          submitted,
          final: last,
          bridge: {
            delegatedTo: "jarvis-a2a",
            baseUrl,
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

  api.registerGatewayMethod("jarvis.codeTask", async ({ params, respond }) => {
    try {
      const requestParams = normalizeGatewayPayload(params);
      const result = await executeJarvisCodeTask(api, "gateway", requestParams);
      respond(true, result.details ?? {});
    } catch (err) {
      respond(false, {
        error: err instanceof Error ? err.message : String(err),
      });
    }
  });

  api.registerGatewayMethod("jarvis.delegateTask", async ({ params, respond }) => {
    try {
      const requestParams = normalizeGatewayPayload(params);
      const result = await executeJarvisCodeTask(api, "gateway", requestParams);
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
          text: "Usage: /jarvis <task>",
        };
      }
      try {
        const result = await executeJarvisCodeTask(api, "command", { task: args, wait: true });
        return { text: result.content[0]?.text || "Delegated to Jarvis." };
      } catch (err) {
        return { text: `Jarvis delegation failed: ${err instanceof Error ? err.message : String(err)}` };
      }
    },
  });
}
