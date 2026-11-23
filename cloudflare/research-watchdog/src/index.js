const OWNER = "chimeremezewisdom6";
const REPO = "Bitget-bot";
const WORKFLOW = "daily-futures-research.yml";
const MAX_AGE_MS = 9 * 60 * 1000;

async function github(path, env, options = {}) {
  const response = await fetch(`https://api.github.com/repos/${OWNER}/${REPO}/${path}`, {
    ...options,
    headers: {
      "Accept": "application/vnd.github+json",
      "Authorization": `Bearer ${env.GH_TOKEN}`,
      "X-GitHub-Api-Version": "2022-11-28",
      ...(options.headers || {})
    }
  });
  const body = await response.text();
  if (!response.ok) throw new Error(`GitHub API ${response.status}: ${body.slice(0, 500)}`);
  return body ? JSON.parse(body) : {};
}

async function watchdog(env, scheduledTime) {
  if (!env.GH_TOKEN) throw new Error("Missing Cloudflare Worker secret GH_TOKEN");

  const data = await github(
    `actions/workflows/${WORKFLOW}/runs?per_page=20`,
    env
  );
  const runs = data.workflow_runs || [];
  const active = runs.filter(run => ["queued", "in_progress", "waiting", "requested"].includes(run.status));

  if (active.length) {
    return { action: "skip_active_run", active_runs: active.length };
  }

  const latestCompleted = runs
    .filter(run => run.status === "completed")
    .sort((a, b) => Date.parse(b.updated_at || b.run_started_at || b.created_at) -
                    Date.parse(a.updated_at || a.run_started_at || a.created_at))[0];

  const latestMs = latestCompleted
    ? Date.parse(latestCompleted.updated_at || latestCompleted.run_started_at || latestCompleted.created_at)
    : 0;
  const ageMs = latestMs ? Date.now() - latestMs : Number.POSITIVE_INFINITY;
  const latestSucceeded = latestCompleted && latestCompleted.conclusion === "success";

  if (latestSucceeded && ageMs < MAX_AGE_MS) {
    return {
      action: "healthy",
      latest_success_utc: new Date(latestMs).toISOString(),
      age_seconds: Math.round(ageMs / 1000)
    };
  }

  await github(`actions/workflows/${WORKFLOW}/dispatches`, env, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ref: "main",
      inputs: { action: "collect" }
    })
  });

  return {
    action: "recovery_dispatched",
    latest_success_utc: latestMs ? new Date(latestMs).toISOString() : null,
    age_seconds: Number.isFinite(ageMs) ? Math.round(ageMs / 1000) : null,
    scheduled_time: scheduledTime || null
  };
}

export default {
  async scheduled(controller, env, ctx) {
    ctx.waitUntil(
      watchdog(env, new Date(controller.scheduledTime).toISOString())
        .then(result => console.log(JSON.stringify({ watchdog: result })))
        .catch(error => console.error("Research watchdog failed:", error.message))
    );
  },

  async fetch(request, env) {
    if (request.method !== "GET") {
      return new Response("Method not allowed", { status: 405 });
    }
    const url = new URL(request.url);
    if (url.pathname !== "/health") {
      return Response.json({ service: "bitget-research-watchdog", status: "online" });
    }
    try {
      const result = await watchdog(env, "manual-health-check");
      return Response.json({ service: "bitget-research-watchdog", status: "ok", ...result });
    } catch (error) {
      return Response.json(
        { service: "bitget-research-watchdog", status: "error", message: error.message },
        { status: 500 }
      );
    }
  }
};
