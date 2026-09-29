import OpenAI from "openai";

/* Provider-agnostic single-shot text completion. Honors AI_PROVIDER
   (openai | claude), the same switch used for insights, so competitor
   suggestions run on whichever model you've selected. */
export async function llmComplete(prompt, { maxTokens = 1024, temperature = 0.4 } = {}) {
  const provider = (process.env.AI_PROVIDER || "openai").trim().toLowerCase();

  if (provider === "claude") {
    const { default: Anthropic } = await import("@anthropic-ai/sdk");
    const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
    // Newer Claude models reject `temperature`, so we don't send it.
    const msg = await anthropic.messages.create({
      model: process.env.ANTHROPIC_MODEL || "claude-sonnet-5",
      max_tokens: maxTokens,
      messages: [{ role: "user", content: prompt }],
    });
    return (msg.content || []).map((b) => b.text || "").join("").trim();
  }

  const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  const response = await client.responses.create({
    model: process.env.OPENAI_MODEL || "gpt-5.2",
    input: prompt,
  });
  return (response.output_text || "").trim();
}

/* Tolerant JSON extraction — models sometimes wrap output in ```json fences,
   add a stray sentence, or get truncated mid-array by the token cap. First try
   a clean parse; if that fails, salvage every complete top-level {...} object so
   a truncated last item doesn't sink the whole list. */
export function parseJsonLoose(text) {
  if (!text) return null;
  const t = String(text).trim()
    .replace(/^```(?:json)?\s*/i, "")
    .replace(/\s*```$/i, "")
    .trim();

  // Walk the string collecting balanced top-level {...} objects, ignoring braces
  // inside strings. Recovers every complete object even from a truncated array.
  const salvage = () => {
    const objects = [];
    let depth = 0;
    let start = -1;
    let inStr = false;
    let esc = false;
    for (let i = 0; i < t.length; i++) {
      const ch = t[i];
      if (inStr) {
        if (esc) esc = false;
        else if (ch === "\\") esc = true;
        else if (ch === '"') inStr = false;
        continue;
      }
      if (ch === '"') {
        inStr = true;
      } else if (ch === "{") {
        if (depth === 0) start = i;
        depth++;
      } else if (ch === "}") {
        if (depth > 0) {
          depth--;
          if (depth === 0 && start !== -1) {
            try {
              objects.push(JSON.parse(t.slice(start, i + 1)));
            } catch {
              /* skip malformed fragment */
            }
            start = -1;
          }
        }
      }
    }
    return objects;
  };

  // 0) Direct parse of the whole payload — preserves the exact shape the model
  //    returned (an object like {storeType, competitors:[…]} OR a bare array),
  //    instead of the array-span match below grabbing a nested array.
  try {
    return JSON.parse(t);
  } catch {
    /* not clean JSON — fall through to extraction */
  }

  // 1) Clean array span.
  const arr = t.match(/\[[\s\S]*\]/);
  if (arr) {
    try {
      return JSON.parse(arr[0]);
    } catch {
      /* truncated — fall through */
    }
  }

  // 2) Looks like an array (possibly truncated) → salvage its objects as a list.
  if (t.startsWith("[")) {
    const objs = salvage();
    if (objs.length) return objs;
  }

  // 3) Clean single object.
  const obj = t.match(/\{[\s\S]*\}/);
  if (obj) {
    try {
      return JSON.parse(obj[0]);
    } catch {
      /* fall through */
    }
  }

  // 4) Last resort — whatever complete objects we can recover.
  const objs = salvage();
  return objs.length ? objs : null;
}
