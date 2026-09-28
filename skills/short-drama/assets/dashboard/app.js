"use strict";
/*
 * Short-drama creator desk.
 *
 * The server parses every document (GET /api/series, /api/episode,
 * /api/search); this file only lays the structures out. Markdown is the one
 * source of truth: structured views are read-only, 编辑原文 opens the raw
 * Markdown, and a save goes through PUT /api/file with the version it was
 * opened at. Nothing here generates, renders or submits production; actions
 * become a sentence copied for the assistant.
 *
 * Every piece of project text is escaped before it reaches innerHTML, and
 * geometry is applied through the CSSOM (data-css), so the page runs under a
 * Content-Security-Policy without inline styles.
 */

const hasDocument = typeof document !== "undefined";
const $ = (selector, root) => (hasDocument ? (root || document).querySelector(selector) : null);
const $$ = (selector, root) => (hasDocument ? Array.from((root || document).querySelectorAll(selector)) : []);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const local = {
  get(key, fallback) { try { const value = localStorage.getItem(`desk.${key}`); return value == null ? fallback : JSON.parse(value); } catch (_error) { return fallback; } },
  set(key, value) { try { localStorage.setItem(`desk.${key}`, JSON.stringify(value)); } catch (_error) { /* private window */ } },
};

/* ================================================================ vocabulary */

const ROOT_ROLES = {
  inputs: "sources", "输入": "sources",
  development: "project", "项目开发": "project",
  bible: "bible", "设定集": "bible",
  episodes: "episodes", "剧集": "episodes",
};

const HIDDEN_ROOTS = new Set([
  ".short-drama", "creator-decisions", "创作者决策", "reviews", "审查",
  "delivery", "交付", "transactions", "事务",
]);

const HIDDEN_FILES = new Set([
  "short-drama.json", "manifest.json", "coverage.json", "delivery-containers.jsonl",
  "screenplay-index.jsonl",
]);

// Reading order inside one group of files: what the creator wrote, then what was built from it.
const SECTION_ORDER = ["story", "project", "sources", "analysis", "cast", "visual", "storyboard", "prompts", "production", "review", "other"];

const CONTENT_META = {
  sources: { label: "原始资料" },
  analysis: { label: "原著分析" },
  project: { label: "项目设定" },
  cast: { label: "人物场景" },
  story: { label: "故事与剧本" },
  prompts: { label: "生成文案" },
  visual: { label: "画面设计" },
  storyboard: { label: "分镜画面" },
  production: { label: "制作成果" },
  review: { label: "审查意见" },
  other: { label: "其他内容" },
};

// Which stage owns a file travels with /api/status. Path rules stay in charge;
// this map only places what they do not recognise.
const OWNER_SECTIONS = {
  "short-drama": "project",
  "short-drama-novel-analyze": "analysis",
  "short-drama-develop": "project",
  "short-drama-write": "story",
  "short-drama-assets": "cast",
  "short-drama-image-prompts": "prompts",
  "short-drama-storyboard": "storyboard",
  "short-drama-video-prompts": "prompts",
  "short-drama-produce": "production",
  "short-drama-edit": "production",
};

// Mirrors project_tool.py's EPISODE_ID_RE.
const EPISODE_ID = /^EP(?:[0-9]{3}|[1-9][0-9]{3,})$/;

// The eight things an episode can have, in the order the work runs.
const STAGES = [
  { key: "script", label: "剧本", doc: "剧本.md", name: "剧本" },
  { key: "settings", label: "设定", doc: "视觉设定.md", name: "视觉设定" },
  { key: "board", label: "分镜", doc: "分镜.md", name: "分镜" },
  { key: "imgp", label: "图片词", doc: "图片提示词.md", name: "图片提示词" },
  { key: "vidp", label: "视频词", doc: "视频提示词.md", name: "视频提示词" },
  { key: "cut", label: "剪辑", doc: "剪辑单.md", name: "剪辑单" },
  { key: "film", label: "成片", doc: "", name: "成片" },
  { key: "review", label: "审查", doc: "", name: "审查意见" },
];
const DOCUMENT_STAGES = STAGES.slice(0, 5);

// The episode workspace's views, in the stage bar's order.
const VIEWS = [
  { key: "", label: "概况" }, { key: "script", label: "剧本" }, { key: "settings", label: "设定" },
  { key: "board", label: "分镜" }, { key: "prompts", label: "提示词" }, { key: "film", label: "成片" },
  { key: "review", label: "审查" },
];
const VIEW_DOCS = { script: "剧本.md", settings: "视觉设定.md", board: "分镜.md", film: "剪辑单.md", review: "review" };

// Ordered far to close. 中近景 is its own rung; the rhythm profile's 近景类
// is 近景、特写、大特写、细节 (the server marks each shot's `close`).
const SCALE_RUNG = { "远景": 1, "全景": 1, "中景": 2, "中近景": 3, "近景": 4, "特写": 5, "细节": 5, "大特写": 6 };

const SEVERITY_LABEL = { must: "必须改", should: "建议改", could: "可以更好" };

const COPYABLE_PROMPT_HEADINGS = new Set(["可复制提示词", "冻结关键帧提示词"]);
const IMAGE_SUFFIXES = new Set(["png", "jpg", "jpeg", "webp", "gif"]);
const VIDEO_SUFFIXES = new Set(["mp4", "webm", "mov"]);
const AUDIO_SUFFIXES = new Set(["wav", "mp3", "m4a", "aac", "flac", "opus"]);

const INTERNAL_KEY_PARTS = [
  "hash", "sha", "path", "ref", "src", "sources", "owner", "schema", "artifact",
  "authority", "lifecycle", "manifest", "checksum", "evidence", "transaction",
  "snapshot", "candidate", "reviewer", "verdict",
];
const INTERNAL_INLINE_VALUE_PATTERNS = [
  /\b[a-f0-9]{20,128}\b/gi,
  /\bshort-drama-[a-z0-9-]+\b/gi,
  /\b(?:[a-z][a-z0-9+.-]*:\/\/|file:)[^\s，。；、）》\]]*/gi,
  /(?:\.short-drama|剧集|设定集|项目开发|输入|创作者决策|审查|交付|事务|episodes|bible|development|inputs|creator-decisions|reviews|delivery|transactions)[\\/][^\s，。；、）》\]]*/gi,
  /(?:^|[\s(（])(?:[/\\~]|\.\.?[/\\]|[a-z]:[/\\])[^\s，。；、）》\]]*/gi,
];
const INTERNAL_WHOLE_VALUE_PATTERNS = [
  /^(?:[^\\/]+[\\/])+(?:[^\\/]+\.(?:md|txt|jsonl?|ya?ml|mp4|mov|webm|png|jpe?g|webp))$/i,
  /^(?:[^\s\\/]+\\){2,}[^\s\\/]+$/,
];
const INTERNAL_VALUE_TOKENS = new Set([
  "absent", "in_progress", "materialized", "not_run", "pass_with_warnings",
  "not_requested", "provisional", "approve_with_notes", "not_evaluated",
  "delivered", "blocked", "candidate", "artifact", "snapshot", "transaction",
  "accepted", "rejected", "approve", "ready", "pending", "revise", "stale",
  "failed", "fail", "pass",
]);
const INTERNAL_EXACT_KEYS = new Set([
  "build_state", "validation_state", "creator_acceptance", "independent_review",
  "delivery_gate", "active_transaction", "last_action", "project_root", "project_id",
]);

const FILE_LABELS = {
  "readme.md": "项目说明", "creative-brief.md": "创作简报", "story-engine.md": "故事引擎",
  "director-brief.md": "导演阐述", "adaptation-map.jsonl": "改编要点", "series-arc.json": "全剧走向",
  "episode-map.jsonl": "分集安排", "characters.jsonl": "人物设定", "looks.jsonl": "造型设定",
  "locations.jsonl": "场景设定", "location-views.jsonl": "场景视角", "props.jsonl": "关键道具",
  "prop-states.jsonl": "道具变化", "episode-card.json": "本集提要", "beats.jsonl": "剧情节拍",
  "screenplay.md": "剧本", "剧本.md": "剧本", "视觉设定.md": "视觉设定", "分镜.md": "分镜",
  "图片提示词.md": "图片提示词", "视频提示词.md": "视频提示词", "剪辑单.md": "剪辑单",
  "screenplay-index.jsonl": "场次索引", "voice-record-sheet.jsonl": "配音稿",
  "occurrences.jsonl": "出场安排", "decisions.jsonl": "画面选择", "continuity.jsonl": "连续性",
  "image-prompt-specs.jsonl": "图片生成方案", "image-prompts.md": "图片生成文案",
  "shots.jsonl": "镜头表", "keyframes.jsonl": "关键帧", "keyframe-prompts.md": "关键帧生成文案",
  "motion-specs.jsonl": "镜头运动", "video-prompts.md": "视频生成文案",
};

// The server speaks a fixed English protocol; each known message becomes a
// sentence that also says what to do next.
const FAILURE_COPY = {
  "file changed since it was opened": "这份内容在别处已经更新，请重新打开后再修改。",
  "text file cannot be opened safely": "这份内容暂时无法打开，请刷新后重试。",
  "text file cannot be replaced safely": "这份内容暂时无法保存，请刷新后重试。",
  "file is locked or not writable": "这份文件被其他程序占用或不可写；关掉正在用它的程序，或检查文件权限。",
  "file is protected and read-only": "这份文件受保护，只能阅读。",
  "media file cannot be opened safely": "这段画面暂时无法打开，请刷新后重试。",
  "file type is not editable text": "这种内容不能在创作台里直接修改。",
  "content exceeds file limit": "内容太长，无法保存。",
  "file exceeds preview limit": "内容太长，无法在这里展示。",
  "media exceeds preview limit": "这段画面太大，无法在这里预览。",
  "path is not a file": "找不到这份内容，可能已被移动。",
  "media path is not a file": "找不到这段画面，可能已被移动。",
  "project not found": "找不到这个项目。",
  "episode not found": "找不到这一集，可能已被移动或改名。",
  "unknown episode": "集号写法不对，应当像 EP001 这样。",
  "search query is too long": "搜索词太长，请缩短一些。",
  "project path changed during the save": "项目位置在保存过程中发生变化，请重新打开。",
  "unsupported preview media": "这种画面格式无法在这里预览。",
  "request body is too large": "内容太长，无法提交。",
  "internal dashboard error": "创作台遇到问题，请刷新后重试。",
  "invalid dashboard response": "创作台收到无效数据，请刷新后重试。",
};

/* ================================================================ pure helpers */

function friendlyFailure(message) {
  return FAILURE_COPY[String(message || "").trim()] || String(message || "");
}

function creatorTitle(title) {
  return typeof title === "string" && title.trim() ? title.trim() : "未命名短剧";
}

function pathSegments(path) {
  return String(path || "").split("/").filter(Boolean);
}

function ownerSection(path, ownership) {
  const owner = ownership?.[path];
  return owner ? OWNER_SECTIONS[owner] || null : null;
}

function creatorSection(path, ownership = null) {
  const parts = pathSegments(path);
  const first = parts[0] || "";
  const lowerFirst = first.toLowerCase();
  const filename = (parts.at(-1) || "").toLowerCase();
  if (["reviews", "审查"].includes(lowerFirst) && filename.endsWith("-审查.md")) return "review";
  if (!parts.length || HIDDEN_ROOTS.has(first) || HIDDEN_ROOTS.has(lowerFirst)) return null;
  if (HIDDEN_FILES.has(filename)) return null;
  if (parts.length === 1) {
    if (filename === "readme.md") return "project";
    return ownerSection(path, ownership) || "other";
  }
  const root = ROOT_ROLES[first] || ROOT_ROLES[lowerFirst];
  if (parts[1] === "source-analysis") return "analysis";
  if (root === "sources" || root === "project") return root;
  if (root === "bible") return "cast";
  if (root !== "episodes") return ownerSection(path, ownership) || "other";
  const area = (parts[2] || "").toLowerCase();
  if (["production", "制作成果"].includes(area)) return "production";
  if (filename === "视觉设定.md") return "cast";
  if (filename === "分镜.md") return "storyboard";
  if (["图片提示词.md", "视频提示词.md"].includes(filename)) return "prompts";
  if (filename === "剧本.md") return "story";
  if (filename === "剪辑单.md") return "production";
  if (/prompts?\.(?:md|jsonl?)$/i.test(filename) || filename.includes("prompt")) return "prompts";
  if (["assets", "资产"].includes(area)) return "visual";
  if (["storyboard", "分镜"].includes(area)) return "storyboard";
  return "story";
}

function creatorProjection(value) {
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (INTERNAL_VALUE_TOKENS.has(normalized) || INTERNAL_WHOLE_VALUE_PATTERNS.some((pattern) => pattern.test(value.trim()))) return undefined;
    let cleaned = value;
    for (const pattern of INTERNAL_INLINE_VALUE_PATTERNS) cleaned = cleaned.replace(pattern, "");
    cleaned = cleaned.replace(/\s{2,}/g, " ").replace(/\s+([，。；、])/g, "$1").trim();
    return cleaned || undefined;
  }
  if (value === null || typeof value !== "object") return value;
  if (Array.isArray(value)) return value.map(creatorProjection).filter((item) => item !== undefined);
  const projected = {};
  for (const [key, raw] of Object.entries(value)) {
    const normalized = String(key)
      .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
      .toLowerCase()
      .replace(/[^a-z0-9一-鿿]+/g, "_")
      .replace(/^_+|_+$/g, "");
    const keyParts = normalized.split("_").filter(Boolean);
    if (INTERNAL_EXACT_KEYS.has(normalized) || INTERNAL_KEY_PARTS.some((part) => keyParts.includes(part))) continue;
    const child = creatorProjection(raw);
    if (child !== undefined) projected[key] = child;
  }
  return projected;
}

function valueIs(axis, wanted) {
  if (typeof axis === "string") return axis === wanted;
  return Boolean(axis && typeof axis === "object" && Number(axis[wanted]) > 0);
}

function axisOnly(axis, allowed) {
  if (typeof axis === "string") return allowed.includes(axis);
  if (!axis || typeof axis !== "object") return false;
  const active = Object.entries(axis).filter(([, count]) => Number(count) > 0).map(([value]) => value);
  return active.length > 0 && active.every((value) => allowed.includes(value));
}

function creatorStatus(lifecycle, recovery = null) {
  if (!lifecycle || typeof lifecycle !== "object") return ["创作中", "neutral"];
  const simple = lifecycle.artifact_state;
  if (typeof simple === "string" || (simple && typeof simple === "object")) {
    if (valueIs(simple, "revise")) return ["需要修改", "danger"];
    if (valueIs(simple, "update_needed")) return ["需要更新", "warning"];
    if (valueIs(simple, "needs_confirmation")) return ["待你确认", "warning"];
    if (axisOnly(simple, ["approved"])) return ["可以导出", "success"];
    if (valueIs(simple, "accepted") || valueIs(simple, "approved")) return ["已采用", "success"];
    return ["创作中", "neutral"];
  }
  if (
    valueIs(lifecycle.build_state, "failed") || valueIs(lifecycle.build_state, "fail") ||
    valueIs(lifecycle.validation_state, "failed") || valueIs(lifecycle.validation_state, "fail") ||
    valueIs(lifecycle.creator_acceptance, "rejected") || valueIs(lifecycle.independent_review, "rejected") ||
    valueIs(lifecycle.independent_review, "revise")
  ) return ["需要修改", "danger"];
  if (recovery?.needed) return ["需要更新", "warning"];
  if (valueIs(lifecycle.build_state, "stale")) return ["需要更新", "warning"];
  if (valueIs(lifecycle.creator_acceptance, "pending")) return ["待你确认", "warning"];
  const accepted = axisOnly(lifecycle.creator_acceptance, ["accepted"]);
  const reviewed = axisOnly(lifecycle.independent_review, ["approve", "approve_with_notes"]);
  const ready = axisOnly(lifecycle.delivery_gate, ["ready", "delivered"]);
  const built = lifecycle.build_state === undefined || axisOnly(lifecycle.build_state, ["materialized"]);
  const valid = lifecycle.validation_state === undefined || axisOnly(lifecycle.validation_state, ["pass", "pass_with_warnings"]);
  if (accepted && reviewed && ready && built && valid) return ["可以导出", "success"];
  const unfinished =
    valueIs(lifecycle.build_state, "absent") || valueIs(lifecycle.build_state, "in_progress") ||
    valueIs(lifecycle.validation_state, "not_run") || valueIs(lifecycle.independent_review, "not_requested") ||
    valueIs(lifecycle.independent_review, "provisional") || valueIs(lifecycle.delivery_gate, "not_evaluated") ||
    valueIs(lifecycle.delivery_gate, "blocked");
  if (accepted && unfinished) return ["已采用", "neutral"];
  if (accepted) return ["已采用", "success"];
  return ["创作中", "neutral"];
}

function mediaKind(fileOrPath) {
  const path = typeof fileOrPath === "string" ? fileOrPath : fileOrPath?.path;
  const suffix = String(path || "").split(".").at(-1).toLowerCase();
  if (IMAGE_SUFFIXES.has(suffix)) return "image";
  if (VIDEO_SUFFIXES.has(suffix)) return "video";
  if (AUDIO_SUFFIXES.has(suffix)) return "audio";
  return "media";
}

function formatBytes(value) {
  const bytes = Number(value) || 0;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(bytes < 10 * 1024 ? 1 : 0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(bytes < 10 * 1024 * 1024 ? 1 : 0)} MB`;
}

function savedContentIsCurrent(submitted, current) {
  return submitted === current;
}

// IDs such as SHOT-EP001-001 are how the documents cite one another, so an
// unmapped name is shown as written: same case, same hyphens.
function fileLabel(path) {
  const name = pathSegments(path).at(-1) || "内容";
  return FILE_LABELS[name.toLowerCase()] || name.replace(/\.(md|jsonl?|txt)$/i, "");
}

function episodeName(path) {
  const parts = pathSegments(path);
  const root = ROOT_ROLES[parts[0]] || ROOT_ROLES[(parts[0] || "").toLowerCase()];
  if (root === "episodes") return parts[1] || "";
  if (creatorSection(path) !== "review") return "";
  const subject = /^(.+)-审查\.md$/i.exec(parts.at(-1))?.[1] || "";
  return EPISODE_ID.test(subject) ? subject : "";
}

function creatorEditable(file) {
  // Mirrors the server's TEXT_EXTENSIONS; the server rejects invalid JSON on save.
  return Boolean(file?.writable && /\.(md|txt|srt|ass|json|jsonl)$/i.test(file.path));
}

const fmt = (seconds) => {
  const total = Math.round(Number(seconds) || 0);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
};
const pct = (share) => `${Math.round((Number(share) || 0) * 100)}%`;
const num = (value) => String(+Number(value || 0).toFixed(2));
const sceneShort = (id) => String(id || "").replace(/^.*-/, "");

/** Parse `#/EP001/board/SHOT-EP001-011?scene=…` into what to show. */
function parseRoute(hash) {
  const raw = String(hash || "").replace(/^#\/?/, "");
  const [path, query] = raw.split("?");
  const parts = path.split("/").filter(Boolean).map((part) => { try { return decodeURIComponent(part); } catch (_error) { return part; } });
  const q = new URLSearchParams(query || "");
  if (parts[0] && EPISODE_ID.test(parts[0])) return { page: "episode", ep: parts[0], view: parts[1] || "", arg: parts[2] || null, q };
  if (["files", "file", "edit"].includes(parts[0])) return { page: parts[0], ep: null, view: "", arg: null, q };
  return { page: "overview", ep: null, view: "", arg: null, q };
}

/** Where a structured view of a document lives, for 返回 from its editor. */
function viewForPath(path) {
  const parts = pathSegments(path);
  const name = parts.at(-1) || "";
  const episode = episodeName(path);
  if (!episode) return "#/";
  if (/-审查\.md$/.test(name)) return `#/${episode}/review`;
  const view = { "剧本.md": "script", "视觉设定.md": "settings", "分镜.md": "board", "图片提示词.md": "prompts/image", "视频提示词.md": "prompts/video", "剪辑单.md": "film" }[name];
  return view ? `#/${episode}/${view}` : `#/${episode}`;
}

/** The next thing an episode needs, as a sentence to hand to the assistant. */
function nextFor(row) {
  const id = row.id;
  if (row.legacy) return { kind: "legacy", rank: 6, text: "旧版格式，按原文阅读", detail: "这一集没有五份创作文档，创作台只列出原文件", ask: "", href: `#/${id}` };
  const must = row.must || [];
  if (must.length) {
    const ids = must.map((item) => item.id).join("、");
    return {
      kind: "fix", rank: 0, text: `处理 ${must.length} 条必须改的审查意见`, detail: must[0].title,
      ask: `请按 ${id} 的审查意见，先改必须改的 ${must.length} 条（${ids}）。`, href: `#/${id}/review`,
    };
  }
  const started = DOCUMENT_STAGES.some((stage) => row.has[stage.key]);
  const missing = DOCUMENT_STAGES.find((stage) => !row.has[stage.key]);
  if (missing) {
    return {
      kind: started ? "write" : "start", rank: started ? 1 : 5, text: `写${missing.name}`,
      ask: `请为 ${id} 写${missing.doc}。`, href: `#/${id}`,
    };
  }
  if (!row.has.cut) return { kind: "cut", rank: 2, text: "出片后写剪辑单", ask: `请为 ${id} 写剪辑单.md。`, href: `#/${id}/film` };
  if (!row.has.film) return { kind: "render", rank: 3, text: "按剪辑单渲染成片", ask: `请按 ${id} 的剪辑单.md 渲染成片。`, href: `#/${id}/film` };
  if (!row.has.review) return { kind: "review", rank: 4, text: "审查这一集", ask: `请审查 ${id}。`, href: `#/${id}` };
  return { kind: "done", rank: 8, text: "可以导出", ask: `请导出 ${id} 的完整制作资料。`, href: `#/${id}` };
}

/** Up to three next steps across the series: must-fix, then the first missing document, then editing. */
function seriesTodos(rows, limit = 3) {
  return rows
    .map((row, order) => ({ row, order, next: nextFor(row) }))
    .filter((item) => item.next.kind !== "done")
    .sort((a, b) => a.next.rank - b.next.rank || a.order - b.order)
    .slice(0, limit);
}

/** A gauge: is the measured value inside what the accepted profile allows? */
function rhythmChecks(metrics, profile, target) {
  const checks = [];
  if (target && metrics.shots) {
    checks.push({ key: "seconds", label: "全集时长", value: metrics.seconds, unit: " 秒", rule: "目标", goal: target, ok: null });
  }
  if (profile && metrics.avg != null) {
    checks.push({ key: "avg", label: "平均镜长", value: metrics.avg, unit: " 秒", rule: "目标", goal: profile.target_avg_shot_seconds, ok: null });
  }
  if (profile && metrics.close != null) {
    checks.push({ key: "close", label: "近景类占比", value: metrics.close, share: true, rule: "不少于", goal: profile.close_shot_share_min, ok: metrics.close >= profile.close_shot_share_min });
  }
  if (profile && metrics.vo != null) {
    checks.push({ key: "vo", label: "旁白占台词", value: metrics.vo, share: true, rule: "不超过", goal: profile.vo_share_max, ok: metrics.vo <= profile.vo_share_max });
  }
  return checks;
}

/** Subtitles the cut list quotes verbatim: the only line-to-shot link trusted. */
function lineShots(cuts) {
  const map = new Map();
  for (const cut of (cuts || []).filter((item) => item.shot)) {
    for (const sub of cut.subs) if (!map.has(squash(sub.text))) map.set(squash(sub.text), cut.shot);
    for (const text of cut.texts) for (const item of text.items) if (!map.has(squash(item))) map.set(squash(item), cut.shot);
  }
  return map;
}
const squash = (text) => String(text || "").replace(/\s/g, "");
function lineShot(map, text) {
  const key = squash(text);
  if (map.has(key)) return map.get(key);
  for (const [line, shot] of map) if (line && key.includes(line)) return shot;
  return null;
}

/* ================================================================ Markdown */

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function button(text, className, action) {
  const node = element("button", className, text);
  node.onclick = action;
  return node;
}

function appendInlineText(node, text) {
  const tokens = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).filter(Boolean);
  for (const token of tokens) {
    if (token.startsWith("`") && token.endsWith("`")) node.append(element("code", "", token.slice(1, -1)));
    else if (token.startsWith("**") && token.endsWith("**")) node.append(element("strong", "", token.slice(2, -2)));
    else node.append(document.createTextNode(token));
  }
}

// What a copy button copies is the block's source text -- quote markers
// removed, lines joined by newlines -- not the rendering.
function copyablePrompt(block) {
  const wrapper = element("div", "copy-block");
  const control = button("复制", "copy-button", () => copyPrompt(control, block));
  control.type = "button";
  control.dataset.copyText = "";
  wrapper.append(block, control);
  return { wrapper, control };
}

async function writeClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (_error) {
    const scratch = element("textarea", "clipboard-scratch");
    scratch.value = text;
    scratch.setAttribute("readonly", "");
    document.body.append(scratch);
    scratch.select();
    let copied = false;
    try { copied = document.execCommand("copy"); } catch (_ignored) { copied = false; }
    scratch.remove();
    return copied;
  }
}

async function copyPrompt(control, block) {
  const copied = await writeClipboard(control.dataset.copyText);
  control.focus({ preventScroll: true });
  if (copied) {
    control.textContent = "已复制";
    control.dataset.state = "copied";
    setTimeout(() => { control.textContent = "复制"; delete control.dataset.state; }, 1600);
    return;
  }
  const range = document.createRange();
  range.selectNodeContents(block);
  getSelection().removeAllRanges();
  getSelection().addRange(range);
  toast("无法直接写入剪贴板，已选中这段提示词，请按 ⌘/Ctrl + C 复制。");
}

function renderMarkdown(content) {
  const fragment = document.createDocumentFragment();
  let list = null;
  let listKind = null;
  let fence = null;
  // Consecutive `>` lines are one blockquote: a copyable prompt is written that way on purpose.
  let quoteNode = null;
  let copyable = false;
  let quoteCopy = null;
  // Markdown comments hold creator notes; closed ones are dropped, an
  // unterminated one is rendered verbatim rather than eating the document.
  let comment = null;
  const closeList = () => { list = null; listKind = null; };
  const closeQuote = () => { quoteNode = null; quoteCopy = null; };
  const paragraph = (text) => {
    const node = element("p");
    appendInlineText(node, text);
    fragment.append(node);
  };
  const codeBlock = (lines) => {
    const pre = element("pre", "code-block");
    pre.append(element("code", "", lines.join("\n")));
    if (!copyable) { fragment.append(pre); return; }
    const { wrapper, control } = copyablePrompt(pre);
    control.dataset.copyText = lines.join("\n");
    fragment.append(wrapper);
  };
  for (let line of content.split("\n")) {
    if (fence !== null) {
      if (/^\s*```/.test(line)) { codeBlock(fence); fence = null; } else fence.push(line);
      continue;
    }
    if (comment !== null) {
      const closeAt = line.indexOf("-->");
      if (closeAt === -1) { comment.push(line); continue; }
      comment = null;
      line = line.slice(closeAt + 3);
      if (!line.trim()) { closeQuote(); continue; }
    }
    if (/^\s*```/.test(line)) { closeList(); closeQuote(); fence = []; continue; }
    let stripped = line;
    for (let previous = null; previous !== stripped;) {
      previous = stripped;
      stripped = stripped.replace(/<!--[\s\S]*?-->/g, "");
    }
    const openAt = stripped.indexOf("<!--");
    if (openAt !== -1) {
      closeList();
      closeQuote();
      const before = stripped.slice(0, openAt);
      if (before.trim()) paragraph(before);
      comment = [stripped.slice(openAt)];
      continue;
    }
    if (stripped !== line) {
      if (!stripped.trim()) { if (!quoteCopy) closeQuote(); continue; }
      line = stripped;
    }
    const heading = /^(#{1,4})\s+(.+)$/.exec(line);
    if (heading) {
      closeList();
      closeQuote();
      const node = element(`h${heading[1].length}`);
      appendInlineText(node, heading[2]);
      fragment.append(node);
      copyable = COPYABLE_PROMPT_HEADINGS.has(heading[2].trim());
      continue;
    }
    const bullet = /^[-*]\s+(.+)$/.exec(line);
    const ordered = /^\d+[.)]\s+(.+)$/.exec(line);
    if (bullet || ordered) {
      closeQuote();
      const kind = bullet ? "ul" : "ol";
      if (!list || listKind !== kind) { list = element(kind); listKind = kind; fragment.append(list); }
      const node = element("li");
      appendInlineText(node, (bullet || ordered)[1]);
      list.append(node);
      continue;
    }
    closeList();
    if (!line.trim()) { if (!quoteCopy) closeQuote(); continue; }
    const quote = /^>\s?(.*)$/.exec(line);
    if (quote) {
      if (quoteNode) quoteNode.append(element("br"));
      else {
        quoteNode = element("blockquote");
        if (copyable) {
          const { wrapper, control } = copyablePrompt(quoteNode);
          quoteCopy = { control, lines: [] };
          fragment.append(wrapper);
        } else {
          fragment.append(quoteNode);
        }
      }
      appendInlineText(quoteNode, quote[1]);
      if (quoteCopy) {
        quoteCopy.lines.push(quote[1]);
        quoteCopy.control.dataset.copyText = quoteCopy.lines.join("\n");
      }
      continue;
    }
    closeQuote();
    paragraph(line);
  }
  if (comment !== null) for (const line of comment) paragraph(line);
  if (fence !== null && fence.length) codeBlock(fence);
  return fragment;
}

// A half-written file must still preview: one truncated record from an
// interrupted agent run should not hide every valid record around it.
function readJsonLines(content) {
  return content.split("\n").map((line, index) => ({ line: index + 1, text: line.trim() })).filter((row) => row.text).map((row) => {
    try { return { line: row.line, record: JSON.parse(row.text) }; }
    catch (error) { return { line: row.line, error: error.message, text: row.text }; }
  });
}

function friendlyKey(key) {
  const labels = {
    id: "编号", name: "名称", title: "标题", description: "说明", summary: "概要",
    character: "人物", character_id: "人物编号", location: "场景", location_id: "场景编号",
    dialogue: "台词", action: "动作", prompt: "生成文案", role: "作用", type: "类型",
    episode_id: "剧集", scene_id: "场次", shot_id: "镜头", beat_id: "剧情节拍",
    objective: "目标", conflict: "冲突", turn: "转折", emotion: "情绪", relationship: "关系",
    costume: "服装", prop: "道具", props: "道具", lighting: "光线", camera: "摄影",
    composition: "构图", duration: "时长", start_boundary: "开始画面", end_boundary: "结束画面",
    boundary_role: "画面位置", continuity_state: "连续性", notes: "备注", value: "内容",
  };
  const normalized = String(key).toLowerCase().replace(/-/g, "_");
  if (labels[normalized]) return labels[normalized];
  if (/[一-鿿]/.test(String(key))) return String(key).replace(/[_-]/g, " ");
  return String(key).replace(/([a-z0-9])([A-Z])/g, "$1 $2").replace(/[_-]+/g, " ").trim() || "补充信息";
}

function appendStructuredValue(node, value) {
  if (Array.isArray(value)) {
    if (!value.length) { node.textContent = "—"; return; }
    const list = element("ul");
    for (const item of value) { const row = element("li"); appendStructuredValue(row, item); list.append(row); }
    node.append(list);
    return;
  }
  if (value && typeof value === "object") {
    const entries = Object.entries(value);
    if (!entries.length) { node.textContent = "—"; return; }
    const list = element("dl");
    for (const [key, child] of entries) {
      const detail = element("dd");
      appendStructuredValue(detail, child);
      list.append(element("dt", "", friendlyKey(key)), detail);
    }
    node.append(list);
    return;
  }
  node.textContent = value === null || value === "" ? "—" : String(value);
}

function structuredCard(value, index) {
  const card = element("article", "structured-card");
  const projected = creatorProjection(value);
  if (projected === undefined || projected === null || typeof projected !== "object") {
    card.append(element("p", "", projected === undefined ? "暂无可展示内容" : String(projected)));
    return card;
  }
  if (index !== null) card.append(element("span", "record-number", `第 ${index + 1} 项`));
  const list = element("dl");
  for (const [key, raw] of Object.entries(projected)) {
    const detail = element("dd");
    appendStructuredValue(detail, raw);
    list.append(element("dt", "", friendlyKey(key)), detail);
  }
  if (!list.childNodes.length) list.append(element("dt", "", "内容"), element("dd", "", "暂无可展示内容"));
  card.append(list);
  return card;
}

function renderDocument(path, content) {
  const host = element("div", "doc");
  try {
    if (/\.md$/i.test(path)) host.append(renderMarkdown(content));
    else if (/\.json$/i.test(path)) host.append(structuredCard(JSON.parse(content), null));
    else if (/\.jsonl$/i.test(path)) {
      readJsonLines(content)
        .filter((row) => !(row.record && typeof row.record === "object" && row.record.record_type === "sources"))
        .forEach((row, index) => host.append(row.error
          ? element("p", "preview-warning", `第 ${row.line} 项内容还不完整，暂时无法展示。`)
          : structuredCard(row.record, index)));
    } else host.append(element("pre", "", content));
  } catch (_error) {
    host.replaceChildren(element("p", "preview-warning", "这份内容还不完整，暂时无法展示。"));
  }
  return host;
}

/* ================================================================ icons */

const IC = {
  search: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/>',
  left: '<path d="m14.5 6-6 6 6 6"/>', right: '<path d="m9.5 6 6 6-6 6"/>', down: '<path d="m6 9.5 6 6 6-6"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>', check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  copy: '<rect x="8.5" y="8.5" width="11" height="11" rx="2"/><path d="M15.5 8.5V6a1.5 1.5 0 0 0-1.5-1.5H6A1.5 1.5 0 0 0 4.5 6v8A1.5 1.5 0 0 0 6 15.5h2.5"/>',
  edit: '<path d="M4.5 19.5h4l10-10a2.1 2.1 0 0 0-4-4l-10 10v4Z"/><path d="m13.5 6.5 4 4"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2.5 12h2M19.5 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4"/>',
  moon: '<path d="M19.5 14.5A8 8 0 0 1 9.5 4.5a8 8 0 1 0 10 10Z"/>',
  play: '<path d="M8 5.5v13l10.5-6.5L8 5.5Z"/>',
  voice: '<path d="M12 4.5a3 3 0 0 0-3 3v4a3 3 0 0 0 6 0v-4a3 3 0 0 0-3-3Z"/><path d="M6 11.5a6 6 0 0 0 12 0M12 17.5v2.5"/>',
  sfx: '<path d="M5 13v-2M9 16V8M13 19V5M17 16V8M21 13v-2"/>',
  text: '<rect x="3.5" y="5.5" width="17" height="13" rx="2"/><path d="M8 10h8M8 14h5"/>',
  lock: '<rect x="5.5" y="10.5" width="13" height="9" rx="2"/><path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5"/>',
  alert: '<path d="M12 4 2.8 19.5h18.4L12 4Z"/><path d="M12 10v4.5M12 17.2v.3"/>',
  film: '<rect x="4.5" y="3.5" width="15" height="17" rx="2"/><path d="M4.5 8h15M4.5 16h15M9 3.5v4.5M15 3.5v4.5M9 16v4.5M15 16v4.5"/>',
  place: '<path d="M12 20.5s-6-5.2-6-10a6 6 0 0 1 12 0c0 4.8-6 10-6 10Z"/><circle cx="12" cy="10.5" r="2.2"/>',
  prop: '<path d="M7 7.5h10l-1 12H8l-1-12Z"/><path d="M9.5 7.5V5.5h5v2"/>',
  person: '<circle cx="12" cy="8.5" r="3.5"/><path d="M5 19.5c1.2-3.4 3.9-5 7-5s5.8 1.6 7 5"/>',
  list: '<path d="M9 6.5h11M9 12h11M9 17.5h11M4.5 6.5h.01M4.5 12h.01M4.5 17.5h.01"/>',
  grid: '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
  doc: '<path d="M7 3.5h7l4 4v13H7z"/><path d="M14 3.5v4h4M9.5 12h6M9.5 15.5h6"/>',
  media: '<rect x="3.5" y="5.5" width="17" height="13" rx="2"/><path d="m10 9.5 4.5 2.5-4.5 2.5z"/>',
};
const icon = (name, cls = "i") => `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${IC[name] || ""}</svg>`;
const fillIcon = (name) => icon(name, "i fill");

/* ================================================================ state */

const S = {
  apiBase: "",
  projects: [],
  project: null,
  series: null,
  tree: null,
  status: null,
  episodes: new Map(),
  theme: local.get("theme", "auto"),
  layout: local.get("layout", "cards"),
  reviewFilter: "all",
  copied: new Set(),
  edit: null,
  lastHash: "",
  renderSequence: 0,
  pendingLine: null,
  palette: { sel: 0, items: [], scope: "ep", timer: null, sequence: 0 },
};

async function api(path, options) {
  const requestPath = S.apiBase && path.startsWith("/api/") ? `${S.apiBase}${path}` : path;
  const response = await fetch(requestPath, options);
  let data;
  try { data = await response.json(); } catch (_error) { throw new Error("invalid dashboard response"); }
  if (!response.ok) {
    const error = new Error((data && data.error) || `HTTP ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return data;
}

async function establishSession() {
  const raw = location.hash.startsWith("#") ? location.hash.slice(1) : "";
  const token = raw && !raw.startsWith("/") ? raw : "";
  const storageKey = "shortDramaApiBase";
  if (!token) {
    try { S.apiBase = sessionStorage.getItem(storageKey) || ""; } catch (_error) { S.apiBase = ""; }
    return;
  }
  const response = await fetch("/api/session", { method: "POST", headers: { "X-Short-Drama-Token": token } });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  if (typeof data.apiBase !== "string" || !data.apiBase.startsWith("/_short_drama/")) throw new Error("本机会话响应无效");
  S.apiBase = data.apiBase;
  try { sessionStorage.setItem(storageKey, S.apiBase); } catch (_error) { /* private window */ }
  history.replaceState(null, "", `${location.pathname}${location.search}#/`);
}

const query = (params) => new URLSearchParams(params).toString();
const mediaUrl = (path) => `${S.apiBase}/api/media/content?${query({ project: S.project, path })}`;

function flatten(nodes, out = []) {
  for (const node of nodes || []) {
    if (node.type === "directory") flatten(node.children, out);
    else out.push(node);
  }
  return out;
}

async function loadProject(id) {
  const [series, tree] = await Promise.all([
    api(`/api/series?${query({ project: id })}`),
    api(`/api/tree?${query({ project: id })}`),
  ]);
  S.project = id;
  S.series = series;
  S.tree = tree;
  S.files = flatten(tree.tree);
  S.episodes = new Map();
  S.copied = new Set(local.get(`copied.${id}`, []));
  local.set("project", id);
}

async function loadEpisode(ep) {
  if (S.episodes.has(ep)) return S.episodes.get(ep);
  // A save may swap S.episodes while this request is in flight; return what was read, not the new empty cache.
  const data = await api(`/api/episode?${query({ project: S.project, ep })}`);
  S.episodes.set(ep, data);
  return data;
}

async function refreshProject() {
  const [series, tree] = await Promise.all([
    api(`/api/series?${query({ project: S.project })}`),
    api(`/api/tree?${query({ project: S.project })}`),
  ]);
  S.series = series;
  S.tree = tree;
  S.files = flatten(tree.tree);
  S.episodes = new Map();
}

/* ================================================================ chrome */

const rowById = (id) => S.series?.episodes.find((row) => row.id === id) || null;
const target = () => S.series?.format?.target_seconds_per_episode || null;
const isDark = () => S.theme === "dark" || (S.theme === "auto" && typeof matchMedia === "function" && matchMedia("(prefers-color-scheme: dark)").matches);

function applyTheme() {
  if (S.theme === "auto") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.dataset.theme = S.theme;
}

function renderTop(route) {
  const rows = S.series?.episodes || [];
  // A raw document or its editor still sits inside its episode.
  const crumbEp = route.ep || episodeName(route.q.get("path") || "");
  const row = crumbEp ? rowById(crumbEp) : null;
  const index = row ? rows.indexOf(row) : -1;
  const title = creatorTitle(S.series?.title);
  const project = S.projects.length > 1
    ? `<select id="projectSelect" aria-label="选择短剧项目">${S.projects.map((item) => `<option value="${esc(item.id)}" ${item.id === S.project ? "selected" : ""}>《${esc(creatorTitle(item.title))}》</option>`).join("")}</select>`
    : `<span class="t">《${esc(title)}》</span>`;
  const viewKey = route.page === "episode" ? route.view : "";
  $("#topbar").innerHTML = `
    <a class="zs-mark" href="#/" aria-label="回到全剧">场</a>
    <nav class="crumbs" aria-label="位置">
      ${S.projects.length > 1 ? `<span class="crumb proj">${project}</span>` : `<a class="crumb proj" href="#/">${project}${row ? "" : '<span class="s">全剧</span>'}</a>`}
      ${row ? `<span class="crumb-sep hide-s">/</span>
        <button class="crumb" id="epMenuBtn" type="button" aria-haspopup="true"><span class="t mono">${esc(row.id)}</span><span class="s">${esc(row.title || "未命名")}</span>${icon("down")}</button>
        <button class="step-btn" type="button" data-go="#/${esc(rows[index - 1]?.id || "")}/${esc(viewKey)}" ${index > 0 ? "" : "disabled"} aria-label="上一集">${icon("left")}</button>
        <button class="step-btn" type="button" data-go="#/${esc(rows[index + 1]?.id || "")}/${esc(viewKey)}" ${index >= 0 && index < rows.length - 1 ? "" : "disabled"} aria-label="下一集">${icon("right")}</button>` : ""}
    </nav>
    <span class="spacer"></span>
    <button class="search-trigger" type="button" data-act="search" aria-label="搜索">${icon("search")}<span>搜索台词、镜头、设定…</span><kbd>⌘K</kbd></button>
    <button class="icon-btn theme-btn" type="button" data-act="theme" aria-label="${isDark() ? "切换到浅色" : "切换到深色"}">${icon(isDark() ? "sun" : "moon")}</button>`;
  const bar = $("#stagebar");
  bar.hidden = !(route.page === "episode" && row) || Boolean(row?.legacy);
  if (bar.hidden) { bar.innerHTML = ""; return; }
  const E = S.episodes.get(row.id);
  const meta = stageMeta(row, E);
  const dot = (key) => {
    if (!key) return "";
    const state = stageState(row, key);
    return `<i class="dot ${state}" aria-hidden="true"></i>`;
  };
  bar.innerHTML = VIEWS.map((view, i) => `${i > 1 ? '<span class="tab-sep"></span>' : ""}<a class="tab" data-stage="${view.key || "home"}" href="#/${esc(row.id)}${view.key ? `/${view.key}` : ""}" ${route.view === view.key ? 'aria-current="page"' : ""}>${dot(view.key)}<span class="lbl">${view.label}</span>${meta[view.key] ? `<span class="meta">${esc(meta[view.key])}</span>` : ""}</a>`).join("");
  const current = $(".tab[aria-current]", bar);
  if (current) bar.scrollLeft = Math.max(0, current.offsetLeft - bar.clientWidth / 2 + current.clientWidth / 2);
}

function stageState(row, key) {
  if (key === "review") return row.review.must ? "warn" : row.has.review ? "on" : "";
  if (key === "prompts") return row.has.imgp && row.has.vidp ? "on" : "";
  if (key === "film") return row.has.film ? "on" : "";
  return row.has[key] ? "on" : "";
}

function stageMeta(row, E) {
  const findings = row.review.must + row.review.should + row.review.could;
  const prompts = E ? (E.imagePrompts?.length || 0) + (E.videoPrompts?.length || 0) : null;
  return {
    "": "",
    script: row.has.script ? (E?.script ? `${E.script.scenes.length} 场` : "已写") : "未写",
    settings: row.has.settings ? (E?.settings ? `${E.settings.items.length} 项` : "已写") : "未写",
    board: row.has.board ? `${row.shots || "—"} 镜` : "未写",
    prompts: row.has.imgp || row.has.vidp ? (prompts != null ? `${prompts} 条` : "已写") : "未写",
    film: row.has.film ? fmt(row.cutSeconds || row.seconds) : row.has.cut ? "未渲染" : "未剪",
    review: row.has.review ? (findings ? `${findings} 条` : "已审") : "无",
  };
}

function episodeMenu(anchor) {
  closeMenus();
  const route = parseRoute(location.hash);
  const menu = document.createElement("div");
  menu.className = "menu";
  menu.id = "epMenu";
  menu.innerHTML = (S.series?.episodes || []).map((row) => `<a href="#/${esc(row.id)}/${esc(route.view)}" ${row.id === route.ep ? 'aria-current="true"' : ""}><span class="menu-id">${esc(row.id)}</span><span class="menu-t">${esc(row.title || "未开始")}</span>${pips(row)}</a>`).join("");
  const box = anchor.getBoundingClientRect();
  menu.dataset.css = `left:${Math.max(8, Math.min(box.left, innerWidth - 300))}px;top:${box.bottom + 6}px`;
  document.body.append(menu);
  applyCss(menu.parentNode);
}
const closeMenus = () => $$(".menu").forEach((menu) => menu.remove());

function pips(row) {
  return `<span class="pips" aria-hidden="true">${STAGES.map((stage) => `<i class="${stage.key === "review" && row.review.must ? "warn" : row.has[stage.key] ? "on" : ""}"></i>`).join("")}</span>`;
}

/* ================================================================ shared bits */

function copyButton(text, key, label = "复制") {
  const done = key && S.copied.has(key);
  return `<button class="btn sm ${done ? "done" : ""}" type="button" data-copy="${esc(text)}" ${key ? `data-key="${esc(key)}"` : ""}>${icon(done ? "check" : "copy")}${done ? "已复制" : label}</button>`;
}
function askButton(ask, primary = true, label = "复制给助手") {
  if (!ask) return "";
  return `<button class="btn sm ${primary ? "primary" : ""}" type="button" data-copy="${esc(ask)}" data-copy-label="已复制，去对话里发送">${icon("copy")}${label}</button>`;
}
/** Distance from a target value, stated without judging it: the profile gives the target, not a tolerance. */
function gapText(value, goal) {
  const d = Math.round((value - goal) * 10) / 10;
  return d === 0 ? "与目标相同" : `${d > 0 ? "多" : "少"} ${num(Math.abs(d))} 秒`;
}
const gap = (value, goal) => `<span class="status">${esc(gapText(value, goal))}</span>`;
function statusMark(ok, words = ["符合", "偏离"]) {
  return `<span class="status ${ok ? "ok" : "warn"}">${icon(ok ? "check" : "alert")}${ok ? words[0] : words[1]}</span>`;
}
function problemNotices(E) {
  return (E.problems || []).map((problem) => `<div class="notice" role="note">${icon("alert")}<span>${esc(problem)}</span></div>`).join("");
}
function editButton(path, at = "", label = "编辑原文", cls = "btn") {
  if (!path) return "";
  const back = location.hash || "#/";
  return `<a class="${cls}" href="#/edit?${esc(query({ path, ...(at ? { at } : {}), back }))}">${icon("edit")}${label}</a>`;
}
function missingView(row, what) {
  const stage = { script: "剧本", settings: "视觉设定", board: "分镜", prompts: "提示词", film: "剪辑单", review: "审查意见" }[what];
  const ask = what === "film" ? `请为 ${row.id} 写剪辑单.md。` : what === "review" ? `请审查 ${row.id}。` : what === "prompts" ? `请为 ${row.id} 写图片提示词.md 和视频提示词.md。` : `请为 ${row.id} 写${stage}.md。`;
  return `<div class="wrap"><div class="empty"><h3>${esc(row.id)} 还没有${stage}</h3><p>在和助手的对话里开始这一步；写好后回到这里就能看到。</p><button class="btn primary" type="button" data-copy="${esc(ask)}" data-copy-label="已复制，去对话里发送">${icon("copy")}复制给助手：${esc(ask)}</button></div></div>`;
}
function rawFallback(E, path, heading) {
  return `<div class="wrap"><div class="head"><div><h2>${esc(heading)}</h2><div class="sub">按原文显示</div></div><div class="actions">${editButton(path)}</div></div>${problemNotices(E)}<div data-raw="${esc(path)}"><div class="loading">正在读取原文…</div></div></div>`;
}

function placeholderSVG(shot) {
  // A framing diagram: how much of a person this shot size shows.
  const sizes = { "远景": [0.22, 0.62], "全景": [0.42, 0.52], "中景": [0.9, 0.62], "中近景": [1.35, 0.72], "近景": [1.9, 0.82], "特写": [3.2, 1.02], "大特写": [5.4, 1.35] };
  const size = sizes[shot.scale];
  let figure;
  if (!size) {
    figure = shot.scale === "细节"
      ? '<rect class="ph-fig" x="27" y="62" width="36" height="36" rx="6" stroke-width="1.5"/><circle class="ph-dot" cx="45" cy="80" r="6"/>'
      : '<text x="45" y="84" text-anchor="middle" font-size="22">?</text>';
  } else {
    const [zoom, y] = size;
    figure = `<g class="ph-fig" transform="translate(45 ${(160 * y * 0.5 + 18).toFixed(1)}) scale(${zoom})" stroke-width="${(1.4 / zoom).toFixed(3)}"><circle cx="0" cy="-26" r="11"/><path d="M-24 22c0-17 10-30 24-30s24 13 24 30v60h-48z"/></g>`;
  }
  return `<svg class="ph" viewBox="0 0 90 160" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><rect class="ph-bg" width="90" height="160"/><path class="ph-edge" d="M0 0h90v160H0z"/>${figure}<text x="45" y="150" text-anchor="middle" font-size="9">${esc(shot.scale || "未写景别")}</text></svg>`;
}

/* ================================================================ episode context */

/** A still's 「运镜」 as the cut list writes it: 固定, or 推近 6%. */
const moveLabel = (cut) => (!cut.move || cut.move.kind === "固定" ? "固定" : cut.move.rate != null ? `${cut.move.kind} ${cut.move.rate}%/秒` : `${cut.move.kind} ${cut.move.amount}%`);

function context(E) {
  const shots = E.board?.shots || [];
  const cuts = E.cutlist?.cuts || [];
  const clipByShot = {};
  for (const cut of cuts) if (E.media.clips[cut.id] && cut.shot && !clipByShot[cut.shot]) clipByShot[cut.shot] = { path: E.media.clips[cut.id], cut };
  const promptByShot = Object.fromEntries((E.videoPrompts || []).map((prompt) => [prompt.shot, prompt]));
  return {
    E,
    shots,
    shot: Object.fromEntries(shots.map((shot) => [shot.id, shot])),
    total: shots.reduce((sum, shot) => sum + shot.sec, 0),
    cuts,
    cutTotal: E.cutlist?.seconds || 0,
    scenes: E.script?.scenes || [],
    findings: E.review?.findings || [],
    profile: S.series?.rhythm || null,
    target: target(),
    clipByShot,
    promptByShot,
    lines: lineShots(cuts),
    frame: (shot) => E.media.frames[shot.id] || null,
  };
}
const findingsFor = (C, id) => C.findings.filter((finding) => finding.targets.includes(id));
const placeOf = (C, sceneId) => C.scenes.find((scene) => scene.id === sceneId)?.place || "";

function thumb(C, shot, withSeconds = true) {
  const frame = C.frame(shot);
  const clip = C.clipByShot[shot.id];
  return `<div class="thumb">${frame ? `<img src="${esc(mediaUrl(frame))}" alt="${esc(shot.title)} 起始帧" loading="lazy">` : placeholderSVG(shot)}${clip ? `<span class="clip" title="已有素材">${fillIcon("play")}</span>` : ""}${withSeconds ? `<span class="sec">${esc(num(shot.sec))}s</span>` : ""}</div>`;
}

/* ================================================================ overview */

function viewOverview() {
  const series = S.series;
  const rows = series.episodes;
  const count = series.format.episode_count || rows.length;
  const perEpisode = target();
  const [statusLabel] = creatorStatus(series.lifecycle);
  const withStage = (key) => rows.filter((row) => row.has[key]).length;
  const cut = rows.filter((row) => row.has.film || row.has.cut).reduce((sum, row) => sum + (row.cutSeconds || 0), 0);
  const whole = perEpisode ? count * perEpisode : 0;
  const todos = seriesTodos(rows);
  const meta = [series.format.aspect_ratio ? `竖屏 ${series.format.aspect_ratio}` : "", `${count} 集`, perEpisode ? `每集目标 ${perEpisode} 秒` : ""].filter(Boolean);
  const kpi = (label, value, of, unit) => `<div class="card kpi"><div class="k">${label}</div><div class="v">${value}<small>/ ${of} ${unit}</small></div><div class="bar"><i data-css="width:${of ? Math.min(100, (value / of) * 100) : 0}%"></i></div></div>`;
  const profile = series.rhythm;
  const projectFiles = (S.files || []).filter((file) => !episodeName(file.path) && creatorSection(file.path, S.status?.ownership));
  return `<div class="wrap" data-view="overview">
  <section class="hero">
    <div class="hero-t">
      <div class="eyebrow">全剧 · ${esc(statusLabel)}</div>
      <h1>《${esc(creatorTitle(series.title))}》</h1>
      <div class="meta">${meta.map((item) => `<span>${esc(item)}</span>`).join("")}</div>
      <div class="kpis">
        ${kpi("剧本", withStage("script"), count, "集")}
        ${kpi("分镜", withStage("board"), count, "集")}
        ${kpi("成片", withStage("film"), count, "集")}
        <div class="card kpi"><div class="k">${whole ? "已剪时长 / 全剧目标" : "已剪时长"}</div><div class="v">${fmt(cut)}${whole ? `<small>/ ${fmt(whole)}</small>` : ""}</div><div class="bar"><i data-css="width:${whole ? Math.min(100, (cut / whole) * 100) : 0}%"></i></div></div>
      </div>
    </div>
    <div class="card next" id="nextSteps">
      <div class="eyebrow">下一步</div>
      ${todos.length ? todos.map((item, i) => `<div class="todo" data-ep="${esc(item.row.id)}"><span class="num ${i ? "soft" : ""}">${i + 1}</span><div><div class="t"><span class="mono">${esc(item.row.id)}</span> · ${esc(item.next.text)}</div><div class="d">${esc(todoDetail(item.row, item.next))}</div></div>
        <div class="acts">${askButton(item.next.ask, i === 0)}<a class="btn sm ghost" href="${esc(item.next.href)}">打开</a></div></div>`).join("") : `<div class="todo"><span class="num">✓</span><div><div class="t">${rows.length ? "每一集都走完了" : "还没有分集"}</div><div class="d">${rows.length ? "可以在对话里请助手导出。" : "在对话里请助手建立第一集。"}</div></div></div>`}
      <p class="foot">创作台只读写 Markdown。写作、生成、渲染都在和助手的对话里确认。</p>
    </div>
  </section>

  <div class="section-t"><h3>分集进度</h3><span class="n">${rows.length} 集 · 点一行进入该集</span></div>
  ${rows.length ? `<div class="card matrix-wrap"><table class="matrix">
    <thead>
      <tr><th colspan="2"></th><th class="group" colspan="5">五份创作文档</th><th class="group" colspan="2">后期</th><th colspan="3"></th></tr>
      <tr><th>集</th><th>集名</th>${STAGES.map((stage) => `<th class="c">${stage.label}</th>`).join("")}<th>时长 / 目标</th><th>下一步</th></tr>
    </thead>
    <tbody>${rows.map((row) => {
      const next = nextFor(row);
      const dim = !DOCUMENT_STAGES.some((stage) => row.has[stage.key]) && !row.legacy;
      return `<tr data-go="#/${esc(row.id)}" data-episode="${esc(row.id)}" class="${dim ? "dim" : ""}"><td class="ep"><a href="#/${esc(row.id)}">${esc(row.id)}</a></td><td class="ttl">${esc(row.title || (row.legacy ? "旧版格式" : "未开始"))}</td>
      ${STAGES.map((stage) => { const warn = stage.key === "review" && row.review.must; const on = row.has[stage.key];
        return `<td><div class="cell"><span class="pip ${warn ? "warn" : on ? "on" : ""}" title="${stage.label}${on ? "：已有" : "：还没有"}" data-stage="${stage.key}" data-on="${on ? 1 : 0}">${warn ? icon("alert") : on ? icon("check") : ""}<span class="sr-only">${stage.label}${warn ? "：有必须改的意见" : on ? "：已有" : "：还没有"}</span></span></div></td>`; }).join("")}
      <td>${row.seconds ? `<div class="dur"><span class="mono">${fmt(row.cutSeconds || row.seconds)}</span>${perEpisode ? `<span class="bar"><i data-css="width:${Math.min(100, ((row.cutSeconds || row.seconds) / (perEpisode * 1.25)) * 100)}%"></i><span class="tgt" data-css="left:80%"></span></span>` : ""}</div>` : '<span class="muted">—</span>'}</td>
      <td class="nextcell">${dim ? '<span class="muted">未开始</span>' : next.kind === "fix" ? `<b>${esc(next.text)}</b>` : esc(next.text)}</td></tr>`; }).join("")}</tbody>
  </table></div>
  <div class="ep-cards">${rows.map((row) => { const next = nextFor(row);
    return `<a class="card ep-card" href="#/${esc(row.id)}" data-episode="${esc(row.id)}"><div class="r1"><span class="ep">${esc(row.id)}</span><span class="ttl">${esc(row.title || "未开始")}</span>${row.review.must ? `<span class="revdot">${icon("alert")}${row.review.must} 必须改</span>` : ""}</div>
    <div class="segs" aria-hidden="true">${STAGES.map((stage) => `<i class="${stage.key === "review" && row.review.must ? "warn" : row.has[stage.key] ? "on" : ""}"></i>`).join("")}</div>
    <div class="r3"><span>${STAGES.filter((stage) => row.has[stage.key]).length}/8 · ${row.seconds ? fmt(row.cutSeconds || row.seconds) : "—"}</span><span>${esc(next.kind === "done" ? "可以导出" : next.text)}</span></div></a>`; }).join("")}</div>` : `<div class="empty"><h3>还没有分集</h3><p>分集建立在「剧集/EP001」这样的文件夹里。</p></div>`}

  <div class="twocol">
    <div><div class="section-t"><h3>节奏档案</h3><span class="n">${profile ? "已接受 · 分镜与审查按它核对" : "尚未接受"}</span></div>
      ${profile ? `<div class="card profile">${[
        ["第一个钩子最迟", `${num(profile.first_hook_seconds)} 秒`], ["目标平均镜长", `${num(profile.target_avg_shot_seconds)} 秒`], ["近景类镜头不少于", pct(profile.close_shot_share_min)],
        ["旁白占台词不超过", pct(profile.vo_share_max)], ["情绪触点最长间隔", `${num(profile.beat_interval_seconds_max)} 秒`], ["每集至少反转", `${profile.opposed_reversals_per_episode_min} 次`],
        ["集尾停在峰值", profile.end_on_peak ? "是" : "否"], ["第一个大爽点不晚于", `第 ${profile.first_major_payoff_by_episode} 集`],
      ].map(([key, value]) => `<div class="row"><span class="k">${key}</span><span class="v">${esc(value)}</span></div>`).join("")}</div>`
      : `<div class="empty"><p>还没有接受节奏档案，所以不对照平均镜长、近景类与旁白占比。</p>${askButton("请为这部剧提出节奏档案，我确认后写入项目。", false, "复制给助手")}</div>`}</div>
    <div><div class="section-t"><h3>人物</h3><span class="n">来自各集视觉设定</span></div>
      ${series.cast.length ? `<div class="card cast">${series.cast.map((person) => `<a class="person" href="#/${esc(person.ep)}/settings/${encodeURIComponent(person.name)}"><span class="tile">${esc(person.name[0] || "?")}</span><div><div class="pn">${esc(person.name)}</div><div class="pd">${esc(person.desc)}</div><div class="pd">${esc(person.ep)} · ${person.shots} 镜</div></div></a>`).join("")}</div>` : '<div class="empty"><p>视觉设定写好后，人物会列在这里。</p></div>'}</div>
  </div>

  <div class="section-t"><h3>项目文件</h3><span class="n">${projectFiles.length} 份</span><a class="more" href="#/files">全部文件 →</a></div>
  ${projectFiles.length ? `<div class="card files-list">${projectFiles.slice(0, 8).map(fileRow).join("")}</div>` : '<p class="muted small">项目层面还没有其他文件。</p>'}
</div>`;
}

function todoDetail(row, next) {
  if (next.kind === "fix" || next.kind === "legacy") return next.detail || "";
  const done = DOCUMENT_STAGES.filter((stage) => row.has[stage.key]).map((stage) => stage.label);
  return done.length ? `已有：${done.join("、")}` : "还没有任何文档";
}

function fileRow(file) {
  const kind = file.type === "media" ? "media" : "doc";
  const section = CONTENT_META[creatorSection(file.path, S.status?.ownership)]?.label || "";
  return `<a class="file-row" href="#/file?${esc(query({ path: file.path }))}">${icon(kind)}<span><div class="fn">${esc(fileLabel(file.path))}</div><div class="fk">${esc([episodeName(file.path), section].filter(Boolean).join(" · "))}</div></span><span class="muted small">${file.type === "media" ? esc(formatBytes(file.size)) : ""}</span></a>`;
}

/* ================================================================ episode home */

function viewEpisode(row, E) {
  const C = context(E);
  const next = nextFor(row);
  const counts = { must: 0, should: 0, could: 0 };
  C.findings.forEach((finding) => counts[finding.sev]++);
  const spoken = C.scenes.flatMap((scene) => scene.blocks).filter((block) => block.k === "line").length;
  const facts = {
    script: E.script ? `${C.scenes.length} 场 · ${spoken} 句台词${E.metrics.vo != null ? ` · 旁白 ${pct(E.metrics.vo)}` : ""}` : "按原文阅读",
    settings: E.settings ? `${E.settings.items.length} 项${E.settings.era.period ? ` · 时代：${E.settings.era.period}` : ""}` : "按原文阅读",
    board: E.board ? `${C.shots.length} 镜 · ${num(C.total)} 秒 · 平均 ${num(E.metrics.avg)} 秒` : "按原文阅读",
    prompts: `图片 ${E.imagePrompts?.length ?? "—"} 条 · 视频 ${E.videoPrompts?.length ?? "—"} 条`,
    film: E.cutlist ? `${C.cuts.length} 段 · ${fmt(C.cutTotal)}${E.media.film ? " · 已渲染成片" : " · 未渲染"}` : E.media.film ? "已有成片" : "按原文阅读",
    review: E.review ? `${E.review.verdict || "已写"} · 必须改 ${counts.must} · 建议改 ${counts.should}` : "按原文阅读",
  };
  const docRows = [
    ["script", "剧本", row.has.script, "剧本.md"],
    ["settings", "视觉设定", row.has.settings, "视觉设定.md"],
    ["board", "分镜", row.has.board, "分镜.md"],
    ["prompts", "提示词", row.has.imgp || row.has.vidp, row.has.imgp && row.has.vidp ? "图片提示词.md · 视频提示词.md" : row.has.imgp ? "图片提示词.md" : "视频提示词.md"],
    ["film", "剪辑与成片", row.has.cut || row.has.film, "剪辑单.md"],
    ["review", "审查", row.has.review, "审查意见"],
  ];
  const checks = rhythmChecks(E.metrics, C.profile, C.target);
  const others = (S.files || []).filter((file) => episodeName(file.path) === row.id && !isStageDocument(file.path));
  const still = C.shots.map((shot) => C.frame(shot)).find(Boolean);
  const poster = E.media.film
    ? `<div class="poster"><video src="${esc(mediaUrl(E.media.film))}#t=0.5" ${still ? `poster="${esc(mediaUrl(still))}"` : ""} preload="metadata" muted playsinline aria-label="成片画面"></video><a class="btn primary play" href="#/${esc(row.id)}/film">${fillIcon("play")}播放成片 ${fmt(C.cutTotal || 0)}</a></div>`
    : C.shots.find((shot) => C.frame(shot))
      ? `<div class="poster"><img src="${esc(mediaUrl(C.frame(C.shots.find((shot) => C.frame(shot)))))}" alt="起始帧"><a class="btn play" href="#/${esc(row.id)}/film">还没有成片</a></div>`
      : `<div class="poster empty-poster"><span class="ph-note">还没有成片。剪辑单写好、渲染之后会在这里播放。</span></div>`;
  return `<div class="wrap" data-view="episode"><div class="ephome">
    <div>${poster}</div>
    <div>
      <div class="head"><div><div class="eyebrow">${esc(row.id)}</div><h2 class="serif">${esc(row.title || "未命名")}</h2><div class="sub">${[C.scenes.length ? `${C.scenes.length} 场` : "", C.shots.length ? `${C.shots.length} 镜` : "", C.shots.length ? `${num(C.total)} 秒${C.target ? `（目标 ${C.target} 秒）` : ""}` : ""].filter(Boolean).join(" · ") || "还没有正文"}</div></div></div>
      ${problemNotices(E)}
      ${next.kind !== "done" ? `<div class="card next"><div class="todo"><span class="num">!</span><div><div class="t">${esc(next.text)}</div><div class="d">${esc(todoDetail(row, next))}</div></div>
        <div class="acts">${askButton(next.ask)}${next.href !== `#/${row.id}` ? `<a class="btn sm" href="${esc(next.href)}">去看</a>` : ""}</div></div></div>` : ""}
      ${checks.length ? `<div class="section-t"><h3>对照节奏档案</h3><span class="n">只做算术，不替你判断好坏</span></div><div class="gauges">${checks.map((check) => gauge(check, C)).join("")}</div>` : ""}
      <div class="section-t"><h3>本集文档</h3></div>
      <div class="card pipeline">${docRows.map(([key, name, present, doc]) => present
        ? `<a class="pl-row" href="#/${esc(row.id)}/${key}"><span class="pip ${key === "review" && counts.must ? "warn" : "on"}">${key === "review" && counts.must ? icon("alert") : icon("check")}</span><span><div class="nm">${name}</div><div class="muted small">${esc(doc)}</div></span><span class="fx">${esc(facts[key])}</span><span class="go">${icon("right")}</span></a>`
        : `<a class="pl-row" href="#/${esc(row.id)}/${key}"><span class="pip"></span><span><div class="nm">${name}</div><div class="muted small">${esc(doc)}</div></span><span class="fx muted">还没有</span><span class="go">${icon("right")}</span></a>`).join("")}</div>
      ${others.length ? `<div class="section-t"><h3>本集其他文件</h3><span class="n">${others.length} 份</span></div><div class="card files-list">${others.map(fileRow).join("")}</div>` : ""}
    </div></div></div>`;
}

function isStageDocument(path) {
  const parts = pathSegments(path);
  return parts.length === 3 && ["剧本.md", "视觉设定.md", "分镜.md", "图片提示词.md", "视频提示词.md", "剪辑单.md"].includes(parts[2]) || /-审查\.md$/.test(parts.at(-1) || "");
}

function viewLegacyEpisode(row) {
  const files = (S.files || []).filter((file) => episodeName(file.path) === row.id && creatorSection(file.path));
  return `<div class="wrap" data-view="episode"><div class="head"><div><div class="eyebrow">${esc(row.id)}</div><h2 class="serif">${esc(row.title || row.id)}</h2><div class="sub">这一集是旧版格式，按原文阅读</div></div></div>
    <div class="card files-list">${files.map(fileRow).join("") || '<p class="muted small">没有可读的文件。</p>'}</div></div>`;
}

function gauge(check, C) {
  const share = Boolean(check.share);
  const value = share ? pct(check.value) : num(check.value);
  const goal = share ? pct(check.goal) : `${num(check.goal)} 秒`;
  let max, fill, zone, tick, foot;
  if (check.key === "seconds") {
    max = check.goal * 1.3; fill = check.value / max; zone = [check.goal * 0.9 / max, check.goal * 1.1 / max]; tick = check.goal / max;
    const diff = check.value - check.goal;
    foot = `${diff >= 0 ? "比目标多" : "比目标少"} ${num(Math.abs(diff))} 秒；±10% 以内算符合`;
  } else if (check.key === "avg") {
    max = Math.max(check.goal * 2, check.value * 1.2); fill = check.value / max; zone = [(check.goal - 0.5) / max, (check.goal + 0.5) / max]; tick = check.goal / max;
    foot = "±0.5 秒以内算符合";
  } else if (check.key === "close") {
    fill = check.value; zone = [check.goal, 1]; tick = check.goal;
    foot = `${C.E.metrics.closeCount || 0} / ${C.shots.length} 镜；${C.E.metrics.unsized} 镜没写景别`;
  } else {
    fill = check.value; zone = [0, check.goal]; tick = check.goal;
    foot = "按可发声字数；[OS] 画外对白不算";
  }
  const clamp = (x) => Math.max(0, Math.min(100, x * 100));
  return `<div class="card gauge" data-gauge="${check.key}" ${check.ok == null ? "" : ` data-ok="${check.ok ? 1 : 0}"`}><div class="k"><span>${check.label}</span>${check.ok == null ? gap(check.value, check.goal) : statusMark(check.ok)}</div>
    <div class="v">${value}<small>${share ? "" : "秒 · "}${check.rule} ${goal}</small></div>
    <div class="bullet" role="img" aria-label="${esc(`${check.label} ${value}，${check.rule} ${goal}`)}"><span class="zone" data-css="left:${clamp(zone[0])}%;width:${clamp(zone[1]) - clamp(zone[0])}%"></span><span class="fill" data-css="width:${clamp(fill)}%"></span><span class="tick" data-css="left:${clamp(tick)}%"></span></div>
    <div class="foot">${esc(foot)}</div></div>`;
}

/* ================================================================ script */

function viewScript(row, E, arg) {
  if (!row.has.script) return missingView(row, "script");
  if (!E.script) return rawFallback(E, E.docs["剧本.md"], "剧本");
  const C = context(E);
  const speakers = {};
  for (const block of C.scenes.flatMap((scene) => scene.blocks)) if (block.k === "line") speakers[block.who] = (speakers[block.who] || 0) + 1;
  const most = Math.max(1, ...Object.values(speakers));
  const shotsIn = (id) => C.shots.filter((shot) => shot.scene === id);
  const mark = (text) => {
    const shot = lineShot(C.lines, text);
    return shot ? `<a class="shotref" href="#/${esc(row.id)}/board/${esc(shot)}" title="在第 ${esc(sceneShort(shot))} 镜">${icon("film")}${esc(sceneShort(shot))}</a>` : "";
  };
  const block = (b) => {
    if (b.k === "action") return `<p class="blk action">${esc(b.text)}</p>`;
    if (b.k === "line") return `<div class="dlg ${b.tag === "VO" ? "vo" : ""}" data-line="${esc(b.text)}"><div class="who">${esc(b.who)}${b.tag ? `<span class="tag ${b.tag.toLowerCase()}">${b.tag === "VO" ? "旁白 VO" : "画外 OS"}</span>` : ""}${mark(b.text)}</div>${b.paren ? `<div class="paren">（${esc(b.paren)}）</div>` : ""}<div class="said">${esc(b.text)}</div></div>`;
    if (b.tag === "画面文字") return `<div class="onscreen" data-line="${esc(b.text)}"><span class="lab">画面文字 · 后期叠加</span>${esc(b.text)}${mark(b.text)}</div>`;
    return `<div class="sfx" data-line="${esc(b.text)}"><span class="tag">${esc(b.tag === "SFX" ? "音效" : b.tag)}</span><span>${esc(b.text)}</span></div>`;
  };
  const sceneFindings = C.findings.filter((finding) => finding.targets.some((id) => /SC\d+$/.test(id)));
  return `<div class="wrap" data-view="script">${problemNotices(E)}<div class="script">
    <aside class="rail left"><div><h4>场次</h4>${C.scenes.map((scene) => { const shots = shotsIn(scene.id);
      return `<a class="scene-link" href="#/${esc(row.id)}/script/${esc(scene.id)}" ${arg === scene.id ? 'aria-current="true"' : ""}><div class="id">${esc(sceneShort(scene.id))}</div><div class="pl">${esc(scene.place)}</div><div class="m">${esc(scene.space)} · ${esc(scene.time)}${shots.length ? ` · ${shots.length} 镜 · ${num(shots.reduce((sum, shot) => sum + shot.sec, 0))} 秒` : ""}</div></a>`; }).join("")}</div>
      <div class="card legend-list"><div><span class="tag vo">旁白 VO</span>内心或旁白</div><div><span class="tag os">画外 OS</span>人在画外说话</div><div><span class="tag plain">音效</span>[SFX]</div><div><span class="stxt">画面文字</span>后期叠加的字</div><div><span class="shotref">${icon("film")}005</span>这句在第几镜（按剪辑单字幕）</div></div>
    </aside>
    <article class="page" aria-label="剧本">
      <div class="page-bar"><span class="mono">剧本.md</span><span>· 按剧本格式排版</span><span class="actions">${editButton(E.docs["剧本.md"], "", "编辑原文", "btn sm")}</span></div>
      <h1>${esc(E.script.title || row.title || row.id)}</h1>
      ${C.scenes.map((scene) => `<div class="slug" id="${esc(scene.id)}"><span class="id">${esc(sceneShort(scene.id))}</span><span class="pl">${esc(scene.space)} · ${esc(scene.place)} · ${esc(scene.time)}</span>${shotsIn(scene.id).length ? `<a class="go btn sm ghost" href="#/${esc(row.id)}/board?scene=${esc(scene.id)}">${shotsIn(scene.id).length} 镜 ${icon("right")}</a>` : ""}</div>${scene.blocks.map(block).join("")}`).join("")}
    </article>
    <aside class="rail right">
      <div><h4>台词</h4><div class="card speakers">${Object.entries(speakers).sort((a, b) => b[1] - a[1]).map(([who, n]) => `<div class="spk"><span>${esc(who)}</span><span class="bar"><i data-css="width:${(n / most) * 100}%"></i></span><span class="c">${n}</span></div>`).join("") || '<span class="muted small">没有台词</span>'}</div></div>
      ${C.profile && E.metrics.vo != null ? `<div><h4>旁白占比</h4>${gauge(rhythmChecks(E.metrics, C.profile, null).find((check) => check.key === "vo"), C)}</div>` : ""}
      ${sceneFindings.length ? `<div><h4>本剧本的审查意见</h4>${sceneFindings.map((finding) => `<a class="card rail-card" href="#/${esc(row.id)}/review/${esc(finding.id)}"><span class="tag ${finding.sev}">${SEVERITY_LABEL[finding.sev]}</span><div class="t">${esc(finding.title)}</div></a>`).join("")}</div>` : ""}
    </aside></div></div>`;
}

/* ================================================================ storyboard */

function stripHTML(C, row, selected, keep) {
  let cursor = 0;
  const bars = C.shots.map((shot) => {
    const rung = SCALE_RUNG[shot.scale];
    const on = !keep || keep(shot);
    const tip = `${shot.title} · ${num(shot.sec)}s · ${shot.scale || "未写景别"}`;
    cursor += shot.sec;
    return `<button class="sb ${rung ? `s${rung}` : "unsized"} ${selected === shot.id ? "sel" : ""} ${on ? "" : "dim"}" type="button" data-css="flex-grow:${Math.max(0.2, shot.sec)}" data-shot="${esc(shot.id)}" data-tip-b="${esc(shot.n)}" data-tip="${esc(tip)}" aria-label="${esc(`${shot.n} ${tip}`)}">${shot.close ? '<span class="cl"></span>' : ""}${esc(String(Number(shot.n) || shot.n))}</button>`;
  }).join("");
  const total = C.total || 1;
  const scenes = [];
  let acc = 0;
  let last = null;
  for (const shot of C.shots) { if (shot.scene !== last) { scenes.push([shot.scene, acc]); last = shot.scene; } acc += shot.sec; }
  const ticks = [];
  const step = total > 120 ? 20 : 10;
  for (let x = 0; x <= total + 0.001; x += step) ticks.push(`<span data-css="left:${(x / total) * 100}%">${x}s</span>`);
  const goal = C.target;
  return `<div class="strip"><div class="strip-scenes">${scenes.map(([id, x], i) => `<span data-css="left:${(x / total) * 100}%;width:${(((scenes[i + 1]?.[1] ?? total) - x) / total) * 100}%">${esc(sceneShort(id) || "未写场次")}<em> ${esc(placeOf(C, id))}</em></span>`).join("")}</div>
    <div class="strip-bars">${bars}</div>
    ${goal && goal <= total ? `<div class="strip-target" data-css="left:${(goal / total) * 100}%"><b>目标 ${goal}s</b></div>` : ""}
    <div class="strip-axis">${ticks.join("")}</div></div>
    <div class="legend">${[["远景/全景", 1], ["中景", 2], ["中近景", 3], ["近景", 4], ["特写/细节", 5], ["大特写", 6]].map(([label, rung]) => `<span><i class="s${rung}"></i>${label}</span>`).join("")}<span><i class="hatch"></i>未写景别</span><span><span class="cl-key"></span>顶部短线 = 近景类</span></div>`;
}

function soundFlags(C, shot) {
  const cut = C.cuts.find((item) => item.shot === shot.id);
  const flags = [];
  if (cut?.subs.length || /台词|对白|一句|VO|OS/.test(shot.sound)) flags.push(`<span class="flag" title="有台词">${icon("voice")}台词</span>`);
  if ((shot.screenText && !/^无/.test(shot.screenText)) || cut?.texts.length) flags.push(`<span class="flag" title="有画面文字">${icon("text")}画面文字</span>`);
  if (cut?.sfx.length) flags.push(`<span class="flag" title="有音效">${icon("sfx")}音效</span>`);
  return flags.join("");
}

function viewBoard(row, E, arg, q) {
  if (!row.has.board) return missingView(row, "board");
  if (!E.board) return rawFallback(E, E.docs["分镜.md"], "分镜");
  const C = context(E);
  const sceneFilter = q.get("scene") || null;
  const entityFilter = q.get("entity") || null;
  const keep = (shot) => (!sceneFilter || shot.scene === sceneFilter) && (!entityFilter || shot.basis.some((entry) => entry.name === entityFilter));
  const list = C.shots.filter(keep);
  const note = sceneFilter ? `场次 ${sceneShort(sceneFilter)}` : entityFilter ? `出现「${entityFilter}」` : "";
  const M = E.metrics;
  const P = C.profile;
  const metric = (label, value, rule, ok) => `<div class="card gauge"><div class="k"><span>${label}</span>${ok === null ? "" : statusMark(ok, ["符合", "留意"])}</div><div class="v">${value}</div><div class="rule">${esc(rule)}</div></div>`;
  const qs = location.hash.includes("?") ? `?${location.hash.split("?")[1]}` : "";
  const cards = list.map((shot) => { const found = findingsFor(C, shot.id);
    return `<article class="card shot ${arg === shot.id ? "sel" : ""}" data-shot="${esc(shot.id)}" id="c-${esc(shot.id)}" tabindex="0" aria-label="${esc(`${shot.n} ${shot.title}`)}">
      ${thumb(C, shot)}
      <div><div class="hd"><span class="no">${esc(shot.n)}</span><span class="tt">${esc(shot.title)}</span></div>
        <div class="pills"><span class="pill">${esc(shot.scale || "未写景别")}</span>${shot.moveKind ? `<span class="pill">${esc(shot.moveKind)}</span>` : ""}<span class="pill">${esc(num(shot.sec))} 秒</span></div>
        <div class="chain"><div><b>起</b><span>${esc(shot.start)}</span></div><div><b>动</b><span>${esc(shot.action)}</span></div><div><b>终</b><span>${esc(shot.end)}</span></div></div>
        <div class="sndrow">${soundFlags(C, shot)}</div></div>
      ${found.length ? `<span class="rev"><span class="revdot ${found[0].sev === "must" ? "" : found[0].sev}">${icon("alert")}${found.length}</span></span>` : ""}
    </article>`; }).join("");
  const rows = list.map((shot) => `<tr data-shot="${esc(shot.id)}" class="${arg === shot.id ? "sel" : ""}"><td><div class="mini">${C.frame(shot) ? `<img src="${esc(mediaUrl(C.frame(shot)))}" alt="">` : placeholderSVG(shot)}</div></td><td class="mono">${esc(shot.n)}</td><td><b>${esc(shot.title)}</b></td><td class="mono">${esc(num(shot.sec))}s</td><td>${esc(shot.scale || "—")}</td><td class="hide-m">${esc(shot.moveKind)}</td><td class="hide-m"><div class="clamp2">${esc(shot.start)} → ${esc(shot.end)}</div></td><td class="hide-m">${soundFlags(C, shot)}</td></tr>`).join("");
  return `<div class="wrap" data-view="board">
  <div class="head"><div><h2>分镜</h2><div class="sub">${C.shots.length} 镜 · ${num(C.total)} 秒${C.scenes.length ? ` · ${C.scenes.length} 场` : ""}</div></div>
    <div class="actions"><div class="seg" role="group" aria-label="布局"><button type="button" data-layout="cards" aria-pressed="${S.layout === "cards"}">${icon("grid")} 卡片</button><button type="button" data-layout="list" aria-pressed="${S.layout === "list"}">${icon("list")} 列表</button></div>
    ${editButton(E.docs["分镜.md"])}</div></div>
  ${problemNotices(E)}
  ${E.board.note ? `<p class="muted small" id="boardNote">${esc(E.board.note)}</p>` : ""}
  <div class="metrics" id="boardMetrics">
    ${metric("总时长", `${num(C.total)}<small> 秒</small>`, C.target ? `目标 ${C.target} 秒 · ${gapText(C.total, C.target)}` : "没有设每集目标", null)}
    ${metric("平均镜长", `${num(M.avg)}<small> 秒</small>`, P ? `目标 ${num(P.target_avg_shot_seconds)} 秒 · ${gapText(M.avg, P.target_avg_shot_seconds)}` : "没有接受节奏档案", null)}
    ${metric("近景类", pct(M.close), P ? `不少于 ${pct(P.close_shot_share_min)}` : "没有接受节奏档案", P ? M.close >= P.close_shot_share_min : null)}
    ${metric("没写景别", `${M.unsized}<small> 镜</small>`, "算不进近景类占比", M.unsized === 0)}
  </div>
  <section class="card strip-card"><div class="strip-head"><h3>节奏条</h3><span class="muted small">宽度 = 时长，颜色 = 景别；点一格看这一镜</span></div>${stripHTML(C, row, arg, sceneFilter || entityFilter ? keep : null)}</section>
  <div class="board-tools"><div class="pills">${[null, ...C.scenes.map((scene) => scene.id)].map((id) => `<a class="pill ${sceneFilter === id && !entityFilter ? "on" : ""}" href="#/${esc(row.id)}/board${id ? `?scene=${esc(id)}` : ""}">${id ? `${esc(sceneShort(id))} ${esc(placeOf(C, id))}` : "全部"}</a>`).join("")}</div>
    ${note ? `<span class="filter-note">筛选：${esc(note)} · ${list.length} 镜 <a class="pill" href="#/${esc(row.id)}/board">${icon("close")}清除</a></span>` : ""}</div>
  ${list.length ? (S.layout === "cards" ? `<div class="shots">${cards}</div>` : `<div class="card table-card"><table class="shot-table"><thead><tr><th></th><th>#</th><th>标题</th><th>时长</th><th>景别</th><th class="hide-m">运镜</th><th class="hide-m">起点 → 终点</th><th class="hide-m">声音</th></tr></thead><tbody>${rows}</tbody></table></div>`) : '<div class="empty"><p>没有符合筛选的镜头。</p></div>'}
  <span hidden data-query="${esc(qs)}"></span>
  </div>`;
}

function renderInspector(row, E, id) {
  const host = $("#inspector");
  const C = E ? context(E) : null;
  const shot = C?.shot[id];
  if (!shot) {
    host.hidden = true;
    host.innerHTML = "";
    $("#scrim").hidden = true;
    document.body.classList.remove("with-inspector");
    return;
  }
  const index = C.shots.indexOf(shot);
  const prompt = C.promptByShot[shot.id];
  const found = findingsFor(C, shot.id);
  const clip = C.clipByShot[shot.id];
  const frame = C.frame(shot);
  const startAt = C.shots.slice(0, index).reduce((sum, item) => sum + item.sec, 0);
  const cut = C.cuts.find((item) => item.shot === shot.id);
  const qs = location.hash.includes("?") ? `?${location.hash.split("?")[1]}` : "";
  const startSlot = shot.refs.find((slot) => slot.kind === "REF" && slot.use === "起始帧");
  let refClass = shot.refState;
  let refLabel = shot.refLabel;
  if (startSlot && !frame) { refClass = "missing"; refLabel = "写了起始帧，但项目里找不到这张图"; }
  else if (frame) { refClass = "bound"; refLabel = "已绑定起始帧"; }
  host.hidden = false;
  document.body.classList.add("with-inspector");
  $("#scrim").hidden = !(typeof matchMedia === "function" && matchMedia("(max-width: 760px)").matches);
  host.innerHTML = `<div class="ins-head"><button class="icon-btn" type="button" data-act="close-ins" aria-label="关闭">${icon("close")}</button><div><div class="id">${esc(shot.id)}</div><div class="t">${esc(shot.title)}</div></div>
    <div class="nav"><button class="icon-btn" type="button" data-shot-nav="${esc(C.shots[index - 1]?.id || "")}" ${index ? "" : "disabled"} aria-label="上一镜">${icon("left")}</button><button class="icon-btn" type="button" data-shot-nav="${esc(C.shots[index + 1]?.id || "")}" ${index < C.shots.length - 1 ? "" : "disabled"} aria-label="下一镜">${icon("right")}</button></div></div>
  <div class="ins-body">
    ${found.map((finding) => `<a class="refstate ${finding.sev === "must" ? "must" : "pending"}" href="#/${esc(row.id)}/review/${esc(finding.id)}"><span class="tag ${finding.sev}">${SEVERITY_LABEL[finding.sev]}</span><span><b>${esc(finding.title)}</b><br><span class="muted">${esc(finding.fix)}</span></span></a>`).join("")}
    <div class="ins-media">
      <div>${clip?.cut.still ? `<div class="thumb"><img src="${esc(mediaUrl(clip.path))}" alt="${esc(shot.title)} 关键帧"></div>` : clip ? `<div class="thumb"><video src="${esc(mediaUrl(clip.path))}#t=${num(clip.cut.in)},${num(clip.cut.out)}" ${frame ? `poster="${esc(mediaUrl(frame))}"` : ""} controls playsinline preload="metadata"></video></div>` : thumb(C, shot, false)}
        <div class="muted small">${clip ? `${clip.cut.still ? `静帧 · ${esc(moveLabel(clip.cut))}` : "素材"} · 剪辑单 ${esc(clip.cut.id)}` : frame ? "起始帧 · 尚无素材" : "未绑定起始帧 · 尚无素材"}</div></div>
      <div class="facts">
        <div class="fact"><div class="k">时长</div><div class="v">${esc(num(shot.sec))} 秒 · 第 ${fmt(startAt)} 起</div></div>
        <div class="fact"><div class="k">场次</div><div class="v">${shot.scene ? `<a href="#/${esc(row.id)}/script/${esc(shot.scene)}">${esc(sceneShort(shot.scene))} ${esc(placeOf(C, shot.scene))}</a>` : "—"}</div></div>
        <div class="fact"><div class="k">景别 / 机位</div><div class="v">${esc(shot.framing || "—")}</div></div>
        <div class="fact"><div class="k">运镜</div><div class="v">${esc(shot.move || "—")}</div></div>
      </div>
    </div>
    ${shot.purpose ? `<div class="ins-sec"><h4>目的</h4><p class="purpose">${esc(shot.purpose)}</p></div>` : ""}
    <div class="ins-sec"><h4>动作</h4><div class="timeline3"><div><b>起点</b>${esc(shot.start || "—")}</div><div class="mid"><b>唯一动作</b>${esc(shot.action || "—")}</div><div><b>终点</b>${esc(shot.end || "—")}</div></div></div>
    <div class="ins-sec"><h4>声音</h4><p>${esc(shot.sound || "—")}</p>${cut?.subs.length ? `<div>${cut.subs.map((sub) => `<span class="subline">「${esc(sub.text)}」</span>`).join("")}</div>` : ""}</div>
    ${shot.screenText || cut?.texts.length ? `<div class="ins-sec"><h4>画面文字</h4>${shot.screenText ? `<p>${esc(shot.screenText)}</p>` : ""}${(cut?.texts || []).map((text) => `<div><span class="stxt">${esc(text.style)}｜${esc(text.items.join("｜"))}</span></div>`).join("")}</div>` : ""}
    <div class="ins-sec"><h4>画面里有</h4><div class="pills">${shot.basis.map((entry) => `<a class="pill" href="#/${esc(row.id)}/settings/${encodeURIComponent(entry.name)}" title="${esc(`控制：${entry.ctl}`)}">${icon(entry.cat === "人物" || entry.cat === "造型" ? "person" : entry.cat === "地点" ? "place" : "prop")}${esc(entry.name)}</a>`).join("") || '<span class="muted">无</span>'}</div></div>
    <div class="ins-sec"><h4>参考图</h4><div class="refstate ${refClass}">${icon(refClass === "bound" ? "check" : refClass === "pending" || refClass === "missing" ? "alert" : "text")}<div><b>${esc(refLabel)}</b>${shot.refs.map((slot) => `<div class="slot">${slot.order}. ${esc(slot.name)}${slot.use ? ` · ${esc(slot.use)}` : ""} · <span class="mono">${esc(slot.path || slot.target)}</span></div>`).join("")}</div></div>
      ${shot.imgs.length ? `<div class="pills">${shot.imgs.map((img) => `<a class="pill id" href="#/${esc(row.id)}/prompts/image?id=${esc(img.id)}" title="${esc(`${img.name} · 控制：${img.ctl}`)}">${esc(img.id)}</a>`).join("")}</div>` : ""}</div>
    ${shot.keyframe ? `<div class="ins-sec"><h4>冻结关键帧提示词<span class="act">${copyButton(shot.keyframe, `kf-${shot.id}`)}</span></h4><div class="prompt clamp" data-act="expand">${esc(shot.keyframe)}</div></div>` : ""}
    ${prompt?.prompt ? `<div class="ins-sec"><h4>视频提示词${prompt.mode ? ` · ${esc(prompt.mode)}` : ""}<span class="act">${copyButton(prompt.prompt, prompt.id)}</span></h4><div class="prompt clamp" data-act="expand">${esc(prompt.prompt)}</div></div>` : ""}
    <div>${editButton(E.docs["分镜.md"], shot.id, "在分镜.md 里编辑这一镜")}</div>
  </div>`;
  host.dataset.back = `#/${row.id}/board${qs}`;
}

/* ================================================================ settings */

function presence(C, item) {
  return C.shots.filter((shot) => shot.basis.some((entry) => entry.name === item.name)).map((shot) => shot.id);
}

function viewSettings(row, E) {
  if (!row.has.settings) return missingView(row, "settings");
  if (!E.settings) return rawFallback(E, E.docs["视觉设定.md"], "视觉设定");
  const C = context(E);
  const settings = E.settings;
  const card = (item) => {
    const seen = new Set(presence(C, item));
    const locked = new Set(item.lock?.shots || []);
    const anchor = item.fields["识别锚点"];
    const rest = Object.entries(item.fields).filter(([key]) => key !== "识别锚点");
    return `<article class="card asset" id="a-${esc(item.name)}" data-entry="${esc(item.name)}">
      <div class="asset-h"><span class="tile">${item.cat === "人物" ? esc(item.name[0]) : icon(item.cat === "地点" ? "place" : item.cat === "造型" ? "person" : "prop")}</span><div><div class="nm">${esc(item.name)}</div><div class="cat">${esc(item.cat)}${item.designators.length ? ` · 画面代称 <span class="mono">${esc(item.designators.join("、"))}</span>` : ""}</div></div></div>
      ${item.overlay ? '<span class="overlay-note">只在后期叠加，不进生成画面</span>' : ""}
      ${item.desc.map((line) => `<p class="desc">${esc(line)}</p>`).join("")}
      ${anchor ? `<div class="anchor"><b>识别锚点</b>${esc(anchor)}</div>` : ""}
      ${rest.map(([key, value]) => `<div class="field"><span class="muted">${esc(key)}：</span>${esc(value)}</div>`).join("")}
      ${item.lock ? `<div class="lock"><div class="ln">${icon("lock")}连续性锁《${esc(item.lock.name)}》</div><span class="surface">${esc(item.lock.surface)}</span><div class="muted small">锁定 ${item.lock.shots.length} 镜 · 每条相关提示词都要逐字带上这段</div></div>` : ""}
      ${C.shots.length ? `<div class="presence"><div class="pk"><span>出现在 ${seen.size} 镜</span>${seen.size ? `<a href="#/${esc(row.id)}/board?entity=${encodeURIComponent(item.name)}">在分镜里筛出 ${icon("right")}</a>` : ""}</div>
        <div class="pstrip" aria-hidden="true">${C.shots.map((shot) => `<i data-css="flex-grow:${Math.max(0.2, shot.sec)}" class="${seen.has(shot.id) ? (locked.has(shot.id) || locked.has("全集") ? "lk" : "on") : ""}" title="${esc(shot.n)}"></i>`).join("")}</div></div>` : ""}
    </article>`;
  };
  return `<div class="wrap" data-view="settings">
    <div class="head"><div><h2>视觉设定</h2><div class="sub">${esc(settings.form)}</div></div><div class="actions">${editButton(E.docs["视觉设定.md"])}</div></div>
    ${problemNotices(E)}
    ${settings.era.period || settings.era.facets.length ? `<section class="card era"><div class="era-l"><div class="eyebrow">时代锚点</div><div class="p">${esc(settings.era.period)}</div><div class="f">画面里的一切都要属于这个年代</div></div>
      <div class="era-r">${settings.era.facets.map((facet) => `<div><div class="k">${esc(facet.k)}</div><div class="v">${esc(facet.v)}</div></div>`).join("")}</div></section>` : ""}
    ${["人物", "造型", "地点", "道具"].map((category) => { const items = settings.items.filter((item) => item.cat === category); if (!items.length) return "";
      return `<div class="section-t"><h3>${category}</h3><span class="n">${items.length}</span>${category === "人物" && C.shots.length ? '<span class="more">出场条：每格一镜，宽度按时长；朱红 = 连续性锁生效</span>' : ""}</div><div class="assets">${items.map(card).join("")}</div>`; }).join("")}
  </div>`;
}

/* ================================================================ prompts */

function viewPrompts(row, E, arg, q) {
  if (!row.has.imgp && !row.has.vidp && !row.has.board) return missingView(row, "prompts");
  const C = context(E);
  const sets = {
    video: (E.videoPrompts || []).map((prompt) => ({ key: prompt.id, id: prompt.id, title: prompt.title, meta: [`${num(prompt.sec)} 秒${prompt.mode ? ` · ${esc(prompt.mode)}` : ""}`, prompt.shot ? `分镜 <a href="#/${esc(row.id)}/board/${esc(prompt.shot)}">${esc(sceneShort(prompt.shot))}</a>` : ""], text: prompt.prompt })),
    keyframe: C.shots.filter((shot) => shot.keyframe).map((shot) => ({ key: `kf-${shot.id}`, id: shot.id, title: shot.title, meta: [`${esc(shot.scale || "未写景别")} · ${num(shot.sec)} 秒`, "冻结关键帧"], text: shot.keyframe })),
    image: (E.imagePrompts || []).map((prompt) => ({ key: prompt.id, id: prompt.id, title: prompt.title, meta: [esc(prompt.use), `被 ${C.shots.filter((shot) => shot.imgs.some((img) => img.id === prompt.id)).length} 镜引用`], text: prompt.prompt })),
  };
  const tab = ["video", "keyframe", "image"].includes(arg) ? arg : sets.video.length ? "video" : sets.keyframe.length ? "keyframe" : "image";
  const list = sets[tab].filter((item) => item.text);
  const done = list.filter((item) => S.copied.has(item.key)).length;
  const nextItem = list.find((item) => !S.copied.has(item.key));
  const open = q.get("id");
  const docFor = { video: E.docs["视频提示词.md"], keyframe: E.docs["分镜.md"], image: E.docs["图片提示词.md"] }[tab];
  const unreadable = { video: row.has.vidp && !E.videoPrompts, image: row.has.imgp && !E.imagePrompts, keyframe: row.has.board && !E.board }[tab];
  return `<div class="wrap" data-view="prompts">
    <div class="head"><div><h2>提示词</h2><div class="sub">整段复制，粘进你的生成工具；一条就是一次生成</div></div>
      <div class="actions"><div class="seg" role="tablist">${[["video", `视频 ${sets.video.length}`], ["keyframe", `关键帧 ${sets.keyframe.length}`], ["image", `图片 ${sets.image.length}`]].map(([key, label]) => `<a role="tab" href="#/${esc(row.id)}/prompts/${key}" ${tab === key ? 'aria-current="page"' : ""}>${label}</a>`).join("")}</div>${editButton(docFor)}</div></div>
    ${problemNotices(E)}
    ${unreadable ? rawFallback(E, docFor, "提示词") : list.length ? `<div class="card copybar"><b>逐条复制</b><span class="bar"><i data-css="width:${(done / list.length) * 100}%"></i></span><span class="muted" id="copyProgress">${done} / ${list.length}</span>
      ${nextItem ? `<button class="btn sm primary" type="button" data-copy="${esc(nextItem.text)}" data-key="${esc(nextItem.key)}" data-next="1">${icon("copy")}复制下一条 · <span class="mono">${esc(nextItem.id.replace(/^(MOTION|SHOT|IMG)-(EP\d+-)?/, ""))}</span></button>` : `<span class="status ok">${icon("check")}全部复制过</span>`}
      <button class="btn sm ghost" type="button" data-act="clear-copied" data-tab="${tab}">清除标记</button><span class="muted lbl-long">标记只存在这台电脑的浏览器里</span></div>
    <div class="plist">${list.map((item) => `<article class="card pcard ${S.copied.has(item.key) ? "copied" : ""}" id="p-${esc(item.id)}" data-key="${esc(item.key)}">
      <div><div class="pid">${esc(item.id)}</div><div class="pt">${esc(item.title)}</div><div class="pm">${item.meta.filter(Boolean).map((line) => `<span>${line}</span>`).join("")}</div></div>
      <div class="ptext ${open === item.id ? "" : "clamp"}" data-act="expand">${esc(item.text)}</div>
      <div class="pact">${copyButton(item.text, item.key)}<span class="cc">${item.text.length} 字符</span></div></article>`).join("")}</div>`
      : `<div class="empty"><h3>这一类还没有提示词</h3><p>${tab === "keyframe" ? "分镜里写了「冻结关键帧提示词」的镜头会列在这里。" : "写好后这里会逐条列出。"}</p></div>`}
  </div>`;
}

/* ================================================================ film */

function viewFilm(row, E, arg, q) {
  if (!row.has.cut && !row.has.film) return missingView(row, "film");
  const C = context(E);
  const CL = E.cutlist;
  const clipsTab = arg === "clips";
  const header = `<div class="head"><div><h2>剪辑与成片</h2><div class="sub">${CL ? `${C.cuts.length} 段 · ${fmt(C.cutTotal)} · 按剪辑单排列` : "只有成片，剪辑单还没写"}</div></div>
      <div class="actions"><div class="seg"><a href="#/${esc(row.id)}/film" ${clipsTab ? "" : 'aria-current="page"'}>成片</a><a href="#/${esc(row.id)}/film/clips" ${clipsTab ? 'aria-current="page"' : ""}>逐镜素材</a></div>${editButton(E.docs["剪辑单.md"], "", "编辑剪辑单")}</div></div>`;
  if (row.has.cut && !CL) return `<div class="wrap" data-view="film">${header}${problemNotices(E)}<div data-raw="${esc(E.docs["剪辑单.md"])}"><div class="loading">正在读取原文…</div></div></div>`;
  if (clipsTab) return `<div class="wrap" data-view="film">${header}${problemNotices(E)}${clipsView(C, row)}</div>`;
  const total = C.cutTotal || 1;
  const X = (t) => `${(t / total) * 100}%`;
  const ticks = [];
  for (let t = 0; t <= total + 0.001; t += total > 90 ? 10 : 5) ticks.push(`<span data-css="left:${X(t)}">${t}</span>`);
  const kindOf = (text) => { for (const scene of C.scenes) for (const block of scene.blocks) if (block.k === "line" && squash(block.text) === squash(text)) return block.tag === "VO" ? "vo" : ""; return ""; };
  const timeline = CL ? `<div class="tl-inner" id="tl">
    <div class="tl-row"><span></span><div class="tl-ruler">${ticks.join("")}</div></div>
    <div class="tl-row"><span class="tl-lab">画面</span><div class="tl-track">${C.cuts.map((cut, i) => `<button class="tl-cut ${i % 2 ? "b" : ""}${cut.still ? " still" : ""}" type="button" data-cut="${esc(cut.id)}" data-css="left:${X(cut.at)};width:calc(${X(cut.sec)} - 2px)" data-tip-b="${esc(cut.n)}" data-tip="${esc(`${cut.title} · ${num(cut.sec)}s${cut.still ? ` · 静帧 ${moveLabel(cut)}` : ""}`)}">${esc(cut.n.slice(-2))}</button>`).join("")}</div></div>
    <div class="tl-row"><span class="tl-lab">字幕</span><div class="tl-track">${C.cuts.flatMap((cut) => cut.subs.map((sub) => { const s = sub.s ?? 0; const e = sub.e ?? cut.sec; return `<span class="tl-sub ${kindOf(sub.text)}" data-css="left:${X(cut.at + s)};width:${X(Math.max(0.1, e - s))}" data-tip="${esc(sub.text)}">${esc(sub.text)}</span>`; })).join("")}</div></div>
    <div class="tl-row"><span class="tl-lab">画面文字</span><div class="tl-track">${C.cuts.flatMap((cut) => cut.texts.map((text) => `<span class="tl-txt" data-css="left:${X(cut.at + text.s)};width:${X(Math.max(0.1, text.e - text.s))}" data-tip-b="${esc(text.style)}" data-tip="${esc(text.items.join(" ｜ "))}">${esc(text.style)}</span>`)).join("")}</div></div>
    <div class="tl-row"><span class="tl-lab">音效</span><div class="tl-track">${C.cuts.flatMap((cut) => cut.sfx.map((sfx) => { const name = sfx.path.split("/").at(-1); return `<span class="tl-sfx" data-css="left:${X(cut.at + sfx.s)}" data-tip="${esc(`${name} · ${num(sfx.gain)} dB`)}"></span><span class="sfx-l" data-css="left:calc(${X(cut.at + sfx.s)} + 10px)">${esc(name.replace(/\.\w+$/, ""))}</span>`; })).join("")}</div></div>
    ${C.cuts.some((cut) => cut.voices.length) ? `<div class="tl-row"><span class="tl-lab">配音</span><div class="tl-track">${C.cuts.flatMap((cut) => cut.voices.map((voice) => { const name = voice.path.split("/").at(-1); return `<span class="tl-sfx tl-voice" data-css="left:${X(cut.at + voice.s)}" data-tip="${esc(`${name}${voice.gain ? ` · ${num(voice.gain)} dB` : ""}`)}"></span><span class="sfx-l" data-css="left:calc(${X(cut.at + voice.s)} + 10px)">${esc(name.replace(/\.\w+$/, ""))}</span>`; })).join("")}</div></div>` : ""}
    <div class="tl-head" id="playhead" data-css="left:64px"></div><div class="tl-hit" id="tlhit" aria-label="点击跳转"></div></div>` : "";
  const highlight = (text, keys) => { let html = esc(text); for (const key of keys || []) html = html.replace(esc(key), `<mark>${esc(key)}</mark>`); return html; };
  const rows = C.cuts.map((cut) => `<tr data-cut="${esc(cut.id)}" id="r-${esc(cut.id)}"><td class="mono">${esc(cut.n)}</td><td><b>${esc(cut.title)}</b><div class="muted small">${cut.still ? `<span class="pill">静帧 · ${esc(moveLabel(cut))}</span> ` : ""}${C.shot[cut.shot] ? `<a href="#/${esc(row.id)}/board/${esc(cut.shot)}">镜 ${esc(sceneShort(cut.shot))}</a> · ` : ""}<span class="mono">${fmt(cut.at)}</span></div></td>
    <td class="mono hide-m">${cut.in.toFixed(2)}–${cut.out.toFixed(2)}</td><td class="mono">${esc(num(cut.sec))}s</td>
    <td>${cut.subs.map((sub) => `<span class="subline">${highlight(sub.text, sub.keys)}</span>`).join("") || '<span class="muted">—</span>'}${cut.texts.map((text) => `<div><span class="stxt">${esc(text.style)}｜${esc(text.items.join("｜"))}</span></div>`).join("")}</td>
    <td class="hide-m">${cut.bed?.path ? `<span class="pill id">环境声 · ${esc(cut.bed.path.split("/").at(-1))}</span>` : ""}${cut.voices.map((voice) => `<span class="pill id">${icon("voice")}${esc(voice.path.split("/").at(-1))}</span>`).join("")}${cut.sfx.map((sfx) => `<span class="pill id">${icon("sfx")}${esc(sfx.path.split("/").at(-1))}</span>`).join("")}</td></tr>`).join("");
  const film = E.media.film;
  const ask = CL ? `请按 ${row.id} 的剪辑单.md 渲染成片。` : "";
  return `<div class="wrap" data-view="film">${header}${problemNotices(E)}<div class="film">
      <div class="player"><div class="frame">${film ? `<video id="film" src="${esc(mediaUrl(film))}" controls playsinline preload="metadata"></video>` : `<span class="ph-note">还没有渲染成片。渲染在对话里确认。</span>`}</div>
        ${CL ? `<div class="now"><span id="nowCut">${C.cuts[0] ? `CUT ${esc(C.cuts[0].n)} · ${esc(C.cuts[0].title)}` : ""}</span><span id="nowTime">0:00 / ${fmt(C.cutTotal)}</span></div>` : ""}
        <div class="muted small">浏览器只播放已有文件；重新渲染在对话里确认。</div>${film ? "" : askButton(ask, false, "复制渲染请求")}</div>
      <div>
        ${CL ? `<div class="deliv">${[CL.target != null ? `目标 ${num(CL.target)} 秒` : "", CL.frame ? `${S.series.format.aspect_ratio ? `${S.series.format.aspect_ratio} · ` : ""}${CL.frame.join("×")}${CL.fps ? ` · ${num(CL.fps)}fps` : ""}` : "", CL.lufs != null ? `响度 ${num(CL.lufs)} LUFS` : "", CL.burn ? "硬字幕" : "不烧字幕"].filter(Boolean).map((item) => `<span class="pill">${esc(item)}</span>`).join("")}</div>
        <section class="card tl">${timeline}</section>
        <div class="card table-card"><table class="cuts"><thead><tr><th>段</th><th>镜头</th><th class="hide-m">入–出</th><th>时长</th><th>字幕与画面文字</th><th class="hide-m">配音与音效</th></tr></thead><tbody>${rows}</tbody></table></div>
        ${CL.unused.length ? `<p class="muted small">未采用：${esc(CL.unused.join("；"))}</p>` : ""}` : '<div class="empty"><p>剪辑单写好后，这里会按段列出字幕、画面文字、配音与音效。</p></div>'}
      </div></div></div>`;
}

function clipsView(C, row) {
  if (!C.shots.length) return '<div class="empty"><p>分镜写好后，每镜一格。</p></div>';
  return `<p class="muted small">每镜素材只按剪辑单「来源」显示；没有来源的镜头保持空位，不按文件名猜。</p><div class="clips">${C.shots.map((shot) => { const clip = C.clipByShot[shot.id];
    return `<a class="cliptile" href="#/${esc(row.id)}/board/${esc(shot.id)}" data-shot-tile="${esc(shot.id)}" data-has-clip="${clip ? 1 : 0}">${clip ? `<div class="thumb">${clip.cut.still ? `<img src="${esc(mediaUrl(clip.path))}" alt="${esc(shot.title)} 关键帧" loading="lazy">` : `<video src="${esc(mediaUrl(clip.path))}#t=${num(clip.cut.in)}" preload="metadata" muted playsinline></video>`}<span class="sec">${esc(num(shot.sec))}s</span></div>` : `<div class="thumb">${placeholderSVG(shot)}<span class="sec">${esc(num(shot.sec))}s</span></div>`}<span class="m"><b>${esc(shot.n)}</b>${clip ? esc(shot.title) : "待生成"}</span></a>`; }).join("")}</div>`;
}

function bindFilm(C) {
  const video = $("#film");
  const tl = $("#tl");
  if (!tl) return;
  const hit = $("#tlhit");
  const head = $("#playhead");
  const total = C.cutTotal || 1;
  // The rendered film can differ from the declared total by a few frames; scale to what plays.
  const scale = () => (video && video.duration && Number.isFinite(video.duration) ? video.duration / total : 1);
  let last = null;
  const place = (t) => {
    head.style.left = `${64 + (Math.min(total, t) / total) * (tl.clientWidth - 64)}px`;
    const cut = C.cuts.find((item) => t >= item.at && t < item.at + item.sec) || C.cuts.at(-1);
    const now = $("#nowTime");
    if (now) now.textContent = `${fmt(t)} / ${fmt(total)}`;
    if (cut && cut.id !== last) {
      last = cut.id;
      const label = $("#nowCut");
      if (label) label.textContent = `CUT ${cut.n} · ${cut.title}`;
      $$(".cuts tr.on, .tl-cut.on").forEach((node) => node.classList.remove("on"));
      document.getElementById(`r-${cut.id}`)?.classList.add("on");
      $(`.tl-cut[data-cut="${CSS.escape(cut.id)}"]`)?.classList.add("on");
      if (video && !video.paused) document.getElementById(`r-${cut.id}`)?.scrollIntoView({ block: "nearest" });
    }
  };
  const sync = () => place(video ? video.currentTime / scale() : 0);
  const seek = (t) => { if (video) { video.currentTime = t * scale(); } place(t); };
  if (video) ["timeupdate", "seeked", "loadedmetadata"].forEach((name) => video.addEventListener(name, sync));
  hit.addEventListener("click", (event) => { const box = hit.getBoundingClientRect(); seek(((event.clientX - box.left) / box.width) * total); });
  $$(".cuts tr[data-cut], .tl-cut").forEach((node) => node.addEventListener("click", (event) => {
    if (event.target.closest("a")) return;
    const cut = C.cuts.find((item) => item.id === node.dataset.cut);
    if (cut) seek(cut.at + 0.01);
  }));
  const focus = parseRoute(location.hash).q.get("cut");
  const wanted = C.cuts.find((item) => item.id === focus);
  if (wanted) { seek(wanted.at + 0.01); document.getElementById(`r-${wanted.id}`)?.scrollIntoView({ block: "center" }); }
  else sync();
}

/* ================================================================ review */

function viewReview(row, E, arg) {
  if (!row.has.review) return missingView(row, "review");
  const review = E.review;
  if (!review || !review.findings.length) {
    return `<div class="wrap" data-view="review"><div class="head"><div><h2>审查意见</h2><div class="sub">按原文显示；修改请交给助手</div></div><div class="actions">${editButton(E.docs.review)}</div></div>${problemNotices(E)}<div data-raw="${esc(E.docs.review)}"><div class="loading">正在读取原文…</div></div></div>`;
  }
  const C = context(E);
  const counts = { must: 0, should: 0, could: 0 };
  review.findings.forEach((finding) => counts[finding.sev]++);
  const list = review.findings.filter((finding) => S.reviewFilter === "all" || finding.sev === S.reviewFilter);
  const where = (id) => {
    if (id.startsWith("SHOT-")) return `<a class="pill id" href="#/${esc(row.id)}/board/${esc(id)}">${icon("film")}镜 ${esc(sceneShort(id))} ${esc(C.shot[id]?.title || "")}</a>`;
    if (id.startsWith("CUT-")) return `<a class="pill id" href="#/${esc(row.id)}/film?cut=${esc(id)}">${icon("sfx")}剪辑 ${esc(sceneShort(id))}</a>`;
    return `<a class="pill id" href="#/${esc(row.id)}/script/${esc(id)}">${icon("text")}剧本 ${esc(sceneShort(id))}</a>`;
  };
  const good = /可以继续/.test(review.verdict);
  return `<div class="wrap" data-view="review">
    <div class="head"><div><h2>审查意见</h2><div class="sub">只读；修改请交给助手</div></div><div class="actions">${editButton(E.docs.review)}</div></div>
    ${problemNotices(E)}
    <section class="card verdict"><span class="vv ${good ? "ok" : "bad"}">${icon(good ? "check" : "alert")}${esc(review.verdict || "已审查")}</span><span class="vm">${review.independent ? "独立审查" : "自检"}${review.scope ? ` · 范围：${esc(review.scope)}` : ""}</span>
      <div class="seg">${[["all", `全部 ${review.findings.length}`], ["must", `必须改 ${counts.must}`], ["should", `建议改 ${counts.should}`], ["could", `可以更好 ${counts.could}`]].map(([key, label]) => `<button type="button" data-rf="${key}" aria-pressed="${S.reviewFilter === key}">${label}</button>`).join("")}</div></section>
    ${list.map((finding) => { const shots = finding.targets.filter((id) => C.shot[id]);
      return `<article class="card finding ${finding.sev}" id="f-${esc(finding.id)}"><span class="stripe"></span><div class="fb">
      <div class="fh"><span class="tag ${finding.sev}">${SEVERITY_LABEL[finding.sev]}</span><span class="t">${esc(finding.title)}</span><span class="rid">${esc(finding.id)}</span></div>
      <div class="fgrid"><span class="k">在哪</span><div class="pills">${finding.targets.map(where).join("") || esc(finding.where || "—")}</div>
        <span class="k">看到了什么</span><div>${esc(finding.evidence || "—")}</div>
        <span class="k">为什么要改</span><div>${esc(finding.impact || "—")}</div>
        <span class="k">改成什么样</span><div class="fix">${esc(finding.fix || "—")}</div></div>
      <div class="ff"><button class="btn sm primary" type="button" data-copy="${esc(`请按 ${row.id} 审查意见 ${finding.id}（${finding.title}）修改：${finding.fix}`)}" data-copy-label="已复制，去对话里发送">${icon("copy")}复制修改请求</button>
        ${shots.length ? `<span class="mini-thumbs">${shots.map((id) => `<a href="#/${esc(row.id)}/board/${esc(id)}" title="${esc(id)}">${thumb(C, C.shot[id], false)}</a>`).join("")}</span>` : ""}</div>
    </div></article>`; }).join("")}
  </div>`;
}

/* ================================================================ files and editor */

function viewFiles() {
  const visible = (S.files || []).filter((file) => creatorSection(file.path, S.status?.ownership));
  const groups = new Map();
  for (const file of visible) {
    const key = episodeName(file.path) || "全剧";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(file);
  }
  const order = [...groups.keys()].sort((a, b) => (a === "全剧" ? -1 : b === "全剧" ? 1 : a.localeCompare(b, "zh-CN", { numeric: true })));
  const rank = (file) => SECTION_ORDER.indexOf(creatorSection(file.path, S.status?.ownership));
  return `<div class="wrap" data-view="files"><div class="head"><div><h2>全部文件</h2><div class="sub">${visible.length} 份 · 工程记录不在这里显示</div></div></div>
    ${(S.tree?.warnings || []).length ? '<div class="notice">部分内容暂时无法读取，已列出其余文件。</div>' : ""}
    ${order.map((key) => `<div class="file-group"><h4>${esc(key)}</h4><div class="card files-list">${groups.get(key).sort((a, b) => rank(a) - rank(b) || fileLabel(a.path).localeCompare(fileLabel(b.path), "zh-Hans-CN")).map(fileRow).join("")}</div></div>`).join("") || '<div class="empty"><p>项目里还没有创作文件。</p></div>'}
  </div>`;
}

function viewFile(q) {
  const path = q.get("path") || "";
  const file = (S.files || []).find((item) => item.path === path);
  const back = episodeName(path) ? `#/${episodeName(path)}` : "#/files";
  return `<div class="wrap" data-view="file"><div class="head"><div><div class="eyebrow">${esc([episodeName(path) || "全剧", CONTENT_META[creatorSection(path)]?.label].filter(Boolean).join(" · "))}</div><h2>${esc(fileLabel(path))}</h2><div class="sub mono">${esc(pathSegments(path).at(-1) || "")}</div></div>
    <div class="actions"><a class="btn ghost" href="${esc(back)}">${icon("left")}返回</a>${file && creatorEditable(file) ? editButton(path) : ""}</div></div>
    <div data-raw="${esc(path)}" data-kind="${file?.type === "media" ? "media" : "text"}"><div class="loading">正在读取…</div></div></div>`;
}

async function fillRaw(sequence) {
  for (const host of $$("[data-raw]")) {
    const path = host.dataset.raw;
    if (!path) { host.innerHTML = '<p class="muted">找不到这份文件。</p>'; continue; }
    try {
      if (host.dataset.kind === "media") {
        const info = await api(`/api/media?${query({ project: S.project, path })}`);
        if (sequence !== S.renderSequence) return;
        const box = element("div", "media-view");
        const node = document.createElement(info.kind === "video" ? "video" : info.kind === "audio" ? "audio" : "img");
        node.src = info.contentUrl;
        if (info.kind === "image") node.alt = fileLabel(path);
        else { node.controls = true; node.preload = "metadata"; if (info.kind === "video") node.playsInline = true; }
        box.append(node, element("span", "muted small", formatBytes(info.size)));
        host.replaceChildren(box);
      } else {
        const data = await api(`/api/file?${query({ project: S.project, path })}`);
        if (sequence !== S.renderSequence) return;
        host.replaceChildren(renderDocument(path, data.content));
      }
    } catch (error) {
      if (sequence !== S.renderSequence) return;
      host.innerHTML = `<div class="notice danger">${icon("alert")}<span>${esc(friendlyFailure(error.message))}</span></div>`;
    }
  }
}

function viewEdit(q) {
  const path = q.get("path") || "";
  return `<div class="wrap" data-view="edit"><div class="editbar" id="editbar">${icon("edit")}<span>正在编辑 <b class="mono">${esc(pathSegments(path).at(-1) || "")}</b>。保存只写回这一份 Markdown，不会触发任何生成。</span>
      <span class="actions"><span class="state" id="editState">正在读取…</span><a class="btn sm ghost" href="${esc(q.get("back") || viewForPath(path))}">返回</a><button class="btn sm primary" type="button" id="saveButton" data-act="save" disabled>保存 <kbd>⌘S</kbd></button></span></div>
    <div id="editNotice"></div>
    <label class="sr-only" for="editor">原文</label><textarea class="editor" id="editor" spellcheck="false" disabled></textarea></div>`;
}

async function openEditor(q, sequence) {
  const path = q.get("path") || "";
  const at = q.get("at") || "";
  try {
    const data = await api(`/api/file?${query({ project: S.project, path })}`);
    if (sequence !== S.renderSequence) return;
    const editable = Boolean(data.writable);
    S.edit = { path, version: data.version, original: data.content, dirty: false, saving: false, writable: editable };
    const editor = $("#editor");
    editor.value = data.content;
    editor.disabled = !editable;
    editor.addEventListener("input", () => setDirty(editor.value !== S.edit.original));
    setDirty(false);
    $("#editState").textContent = editable ? "已载入" : "只读";
    if (at) {
      const index = data.content.indexOf(`## ${at}`);
      if (index >= 0) {
        // Measure the wrapped height of everything above the heading, so the
        // shot lands at the top however long its preceding lines wrap.
        editor.value = data.content.slice(0, index);
        const above = editor.scrollHeight;
        editor.value = data.content;
        editor.focus({ preventScroll: true });
        editor.setSelectionRange(index, index);
        editor.scrollTop = Math.max(0, above - 40);
      }
    } else if (editable) editor.focus({ preventScroll: true });
  } catch (error) {
    if (sequence !== S.renderSequence) return;
    $("#editState").textContent = "";
    $("#editNotice").innerHTML = `<div class="notice danger">${icon("alert")}<span>${esc(friendlyFailure(error.message))}</span></div>`;
  }
}

function setDirty(dirty) {
  if (!S.edit) return;
  S.edit.dirty = dirty;
  const save = $("#saveButton");
  if (save) save.disabled = !S.edit.writable || S.edit.saving || !dirty;
  const state = $("#editState");
  if (state && !S.edit.saving) state.textContent = dirty ? "有未保存的修改" : state.textContent === "有未保存的修改" ? "已保存" : state.textContent;
  document.title = `${dirty ? "● " : ""}${document.title.replace(/^● /, "")}`;
}

async function save() {
  const edit = S.edit;
  if (!edit || !edit.dirty || edit.saving || !edit.writable) return;
  const editor = $("#editor");
  const content = editor.value;
  edit.saving = true;
  setDirty(true);
  $("#editState").textContent = "正在保存…";
  try {
    const result = await api(`/api/file?${query({ project: S.project, path: edit.path })}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, expectedVersion: edit.version }),
    });
    if (S.edit !== edit) return;
    // Structured views must never show the text from before this save.
    S.episodes = new Map();
    edit.version = result.version;
    edit.original = content;
    edit.saving = false;
    $("#editNotice").innerHTML = "";
    $("#editState").textContent = `已保存 · ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
    setDirty(!savedContentIsCurrent(content, editor.value));
    toast("已保存。结构视图会按新内容重新读取。");
    try { await refreshProject(); } catch (_error) { toast("内容已保存，但刷新失败，请稍后重试"); }
  } catch (error) {
    if (S.edit !== edit) return;
    edit.saving = false;
    setDirty(true);
    $("#editState").textContent = "没有保存";
    const conflict = error.status === 409 || /changed since it was opened/.test(error.message);
    $("#editNotice").innerHTML = `<div class="notice danger" id="saveError" data-conflict="${conflict ? 1 : 0}">${icon("alert")}<span>${esc(conflict ? "这份文件在别处改过了，你的修改没有保存。先复制你的修改，再载入最新版本合并。" : friendlyFailure(error.message))}</span>
      ${conflict ? `<span class="actions"><button class="btn sm" type="button" data-act="copy-draft">${icon("copy")}复制我的修改</button><button class="btn sm primary" type="button" data-act="reload-latest">载入最新版本</button></span>` : ""}</div>`;
  }
}

/* ================================================================ search */

function openPalette(initial = "") {
  const host = $("#palette");
  const route = parseRoute(location.hash);
  S.palette.scope = route.ep ? "ep" : "series";
  S.palette.ep = route.ep;
  host.hidden = false;
  host.innerHTML = `<div class="pal"><div class="pal-in">${icon("search")}<input id="palq" placeholder="搜索台词、镜头、设定、提示词、审查…" autocomplete="off" aria-label="搜索"><kbd>esc</kbd></div>
    <div class="pal-scope">${route.ep ? `<button class="pill ${S.palette.scope === "ep" ? "on" : ""}" type="button" data-scope="ep">本集 ${esc(route.ep)}</button>` : ""}<button class="pill ${S.palette.scope === "series" ? "on" : ""}" type="button" data-scope="series">全剧</button></div>
    <div class="pal-res" id="palres" role="listbox"></div>
    <div class="pal-foot"><span>↑↓ 选择</span><span>↵ 打开</span><span>搜索只读，不改任何文件</span></div></div>`;
  const input = $("#palq");
  input.value = initial;
  input.focus();
  input.addEventListener("input", () => { S.palette.sel = 0; scheduleSearch(); });
  input.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      S.palette.sel = Math.max(0, Math.min(S.palette.items.length - 1, S.palette.sel + (event.key === "ArrowDown" ? 1 : -1)));
      paintResults(input.value, true);
    }
    if (event.key === "Enter" && S.palette.items[S.palette.sel]) pick(S.palette.items[S.palette.sel]);
  });
  scheduleSearch(0);
}

function scheduleSearch(delay = 140) {
  clearTimeout(S.palette.timer);
  S.palette.timer = setTimeout(runSearch, delay);
}

async function runSearch() {
  const input = $("#palq");
  if (!input) return;
  const text = input.value.trim();
  const sequence = ++S.palette.sequence;
  if (!text) { S.palette.items = []; paintResults(""); return; }
  try {
    const params = { project: S.project, q: text, scope: S.palette.scope };
    if (S.palette.scope === "ep" && S.palette.ep) params.ep = S.palette.ep;
    const data = await api(`/api/search?${query(params)}`);
    if (sequence !== S.palette.sequence) return;
    S.palette.items = data.hits;
    paintResults(text);
  } catch (error) {
    if (sequence !== S.palette.sequence) return;
    $("#palres").innerHTML = `<div class="pal-empty">${esc(friendlyFailure(error.message))}</div>`;
  }
}

function snippet(hit) {
  const text = hit.snippet;
  const at = hit.at;
  if (at < 0) return esc(text);
  return `${hit.clipped ? "…" : ""}${esc(text.slice(0, at))}<mark>${esc(text.slice(at, at + hit.len))}</mark>${esc(text.slice(at + hit.len))}`;
}

function paintResults(text, keepScroll = false) {
  const host = $("#palres");
  if (!host) return;
  if (!text) {
    host.innerHTML = '<div class="pal-g">可以搜</div><div class="pal-hint">一句台词 · 镜号「014」· 人物名 · 道具 · 画面文字 · 审查意见</div>';
    return;
  }
  const hits = S.palette.items;
  if (!hits.length) { host.innerHTML = `<div class="pal-empty">没有找到「${esc(text)}」</div>`; return; }
  const groups = [...new Set(hits.map((hit) => hit.g))];
  host.innerHTML = groups.map((group) => `<div class="pal-g">${esc(group)}</div>${hits.map((hit, index) => ({ hit, index })).filter((item) => item.hit.g === group).map(({ hit, index }) => {
    const inTitle = hit.field !== "x";
    return `<div class="pal-item" role="option" data-i="${index}" aria-selected="${index === S.palette.sel}"><span class="w">${S.palette.scope === "series" ? `${esc(hit.ep)} · ` : ""}${hit.field === "w" ? snippet(hit) : esc(hit.w)}</span><span class="x">${hit.field === "t" ? snippet(hit) : esc(hit.t)}${inTitle ? "" : `<span class="sn">${snippet(hit)}</span>`}</span></div>`;
  }).join("")}`).join("");
  $$(".pal-item", host).forEach((node) => node.addEventListener("click", () => pick(S.palette.items[Number(node.dataset.i)])));
  const selected = $('.pal-item[aria-selected="true"]', host);
  if (keepScroll && selected) selected.scrollIntoView({ block: "nearest" });
}

function hitHref(hit) {
  const base = `#/${hit.ep}`;
  if (hit.view === "board") return `${base}/board/${hit.arg}`;
  if (hit.view === "script") return `${base}/script/${hit.arg}`;
  if (hit.view === "settings") return `${base}/settings/${encodeURIComponent(hit.arg)}`;
  if (hit.view === "prompts") return `${base}/prompts/${hit.arg}?id=${encodeURIComponent(hit.id)}`;
  if (hit.view === "review") return `${base}/review/${hit.arg}`;
  if (hit.view === "film") return `${base}/film?cut=${encodeURIComponent(hit.cut || "")}`;
  return base;
}

function pick(hit) {
  closePalette();
  S.pendingLine = hit.line || null;
  go(hitHref(hit));
}
const closePalette = () => { const host = $("#palette"); host.hidden = true; host.innerHTML = ""; };

/* ================================================================ render */

function applyCss(root) {
  // Geometry goes through the CSSOM, which the page's CSP allows; inline style attributes it does not.
  for (const node of $$("[data-css]", root)) {
    node.style.cssText = node.dataset.css;
    node.removeAttribute("data-css");
  }
}

function go(hash) {
  if (location.hash === hash) render();
  else location.hash = hash;
}

function showError(message) {
  $("#view").innerHTML = `<div class="wrap"><div class="notice danger" id="notices">${icon("alert")}<span>${esc(message)}</span></div></div>`;
  $("#view").dataset.state = "error";
}

async function render() {
  const sequence = ++S.renderSequence;
  const route = parseRoute(location.hash);
  closeMenus();
  if (!S.series) return;
  const view = $("#view");
  if (route.page !== "edit") S.edit = null;
  view.dataset.state = "loading";
  let E = null;
  const row = route.ep ? rowById(route.ep) : null;
  if (route.page === "episode" && row) {
    if (!S.episodes.has(row.id)) {
      renderTop(route);
      view.innerHTML = '<div class="loading">正在读取这一集…</div>';
    }
    try { E = await loadEpisode(row.id); }
    catch (error) { if (sequence === S.renderSequence) showError(friendlyFailure(error.message)); return; }
    if (sequence !== S.renderSequence) return;
  }
  renderTop(route);
  let html;
  if (route.page === "files") html = viewFiles();
  else if (route.page === "file") html = viewFile(route.q);
  else if (route.page === "edit") html = viewEdit(route.q);
  else if (route.page === "episode" && !row) html = `<div class="wrap"><div class="empty"><h3>没有 ${esc(route.ep)} 这一集</h3><p>它可能已被移动或改名。</p><a class="btn" href="#/">回到全剧</a></div></div>`;
  else if (route.page === "episode" && row.legacy) html = viewLegacyEpisode(row);
  else if (route.page === "episode") {
    const args = [row, E, route.arg, route.q];
    switch (route.view) {
      case "script": html = viewScript(...args); break;
      case "settings": html = viewSettings(...args); break;
      case "board": html = viewBoard(...args); break;
      case "prompts": html = viewPrompts(...args); break;
      case "film": html = viewFilm(...args); break;
      case "review": html = viewReview(...args); break;
      default: html = viewEpisode(...args);
    }
  } else html = viewOverview();
  view.innerHTML = html;
  applyCss(view);
  applyCss($("#topbar"));
  const viewLabel = VIEWS.find((item) => item.key === route.view)?.label || "";
  document.title = `${route.ep ? `${route.ep} ${viewLabel} · ` : ""}《${creatorTitle(S.series.title)}》· 短剧创作台`;
  renderInspector(row, E, route.page === "episode" && route.view === "board" ? route.arg : null);
  applyCss($("#inspector"));
  if (route.page === "episode" && route.view === "film" && E) bindFilm(context(E));
  if (route.page === "edit") await openEditor(route.q, sequence);
  if (sequence !== S.renderSequence) return;
  view.dataset.route = location.hash || "#/";
  view.dataset.state = "ready";
  afterRender(route);
  await fillRaw(sequence);
}

function afterRender(route) {
  let node = null;
  if (route.view === "script" && route.arg) node = document.getElementById(route.arg);
  if (route.view === "board" && route.arg) node = document.getElementById(`c-${route.arg}`);
  if (route.view === "settings" && route.arg) node = document.getElementById(`a-${route.arg}`);
  if (route.view === "review" && route.arg) node = document.getElementById(`f-${route.arg}`);
  if (route.view === "prompts" && route.q.get("id")) node = document.getElementById(`p-${route.q.get("id")}`);
  if (S.pendingLine) {
    const line = $$("[data-line]").find((item) => item.dataset.line === S.pendingLine);
    if (line) { node = line; line.classList.add("hl"); }
    S.pendingLine = null;
  }
  if (node) {
    const target = node;
    requestAnimationFrame(() => {
      target.scrollIntoView({ block: route.view === "board" ? "nearest" : "start" });
      if (!target.classList.contains("hl")) { target.classList.add("flash"); setTimeout(() => target.classList.remove("flash"), 1300); }
    });
  } else if (!(route.view === "board" && route.arg) && route.page !== "edit") scrollTo(0, 0);
}

function toast(message) {
  const host = $("#toast");
  host.textContent = message;
  host.classList.add("show");
  clearTimeout(host.hideTimer);
  host.hideTimer = setTimeout(() => host.classList.remove("show"), 2400);
}

/* ================================================================ events */

async function onClick(event) {
  const node = event.target;
  if (!node.closest("#epMenu") && !node.closest("#epMenuBtn")) closeMenus();
  if (node.closest("#epMenuBtn")) { episodeMenu(node.closest("#epMenuBtn")); return; }
  if (node.id === "palette") { closePalette(); return; }
  if (node.id === "scrim") { go($("#inspector").dataset.back || location.hash.split("/SHOT-")[0]); return; }
  const scope = node.closest("[data-scope]");
  if (scope) { S.palette.scope = scope.dataset.scope; $$(".pal-scope .pill").forEach((pill) => pill.classList.toggle("on", pill === scope)); S.palette.sel = 0; scheduleSearch(0); return; }
  const copy = node.closest("[data-copy]");
  if (copy) {
    const copied = await writeClipboard(copy.dataset.copy);
    if (copy.dataset.key) {
      S.copied.add(copy.dataset.key);
      local.set(`copied.${S.project}`, [...S.copied]);
    }
    toast(copied ? (copy.dataset.copyLabel || `已复制 · ${copy.dataset.copy.length} 字符`) : "浏览器拒绝了剪贴板，请手动选中复制");
    if (copy.dataset.key) {
      const route = parseRoute(location.hash);
      const next = copy.dataset.next ? copy.dataset.key : null;
      await render();
      if (next) document.getElementById(`p-${next.replace(/^kf-/, "")}`)?.scrollIntoView({ block: "center" });
      if (route.view !== "prompts") $(`#inspector [data-key="${CSS.escape(copy.dataset.key)}"]`)?.focus();
    }
    return;
  }
  const jump = node.closest("[data-go]");
  if (jump && jump.dataset.go && !jump.disabled && !node.closest("a")) { go(jump.dataset.go); return; }
  const nav = node.closest("[data-shot-nav]");
  if (nav && nav.dataset.shotNav) { go(shotHref(nav.dataset.shotNav)); return; }
  const action = node.closest("[data-act]")?.dataset.act;
  if (action === "search") { openPalette(); return; }
  if (action === "theme") { S.theme = isDark() ? "light" : "dark"; local.set("theme", S.theme); applyTheme(); renderTop(parseRoute(location.hash)); return; }
  if (action === "save") { save(); return; }
  if (action === "close-ins") { go($("#inspector").dataset.back); return; }
  if (action === "copy-draft") { const ok = await writeClipboard($("#editor").value); toast(ok ? "已复制你的修改" : "浏览器拒绝了剪贴板，请手动选中复制"); return; }
  if (action === "reload-latest") {
    if (!confirm("载入最新版本会丢掉编辑框里还没保存的修改。确定吗？")) return;
    S.edit.dirty = false;
    render();
    return;
  }
  if (action === "clear-copied") {
    const tab = node.closest("[data-act]").dataset.tab;
    const keys = new Set($$(".pcard").map((card) => card.dataset.key));
    for (const key of [...S.copied]) if (keys.has(key)) S.copied.delete(key);
    local.set(`copied.${S.project}`, [...S.copied]);
    if (tab) render();
    return;
  }
  if (action === "expand") { node.closest("[data-act]").classList.toggle("clamp"); return; }
  const layout = node.closest("[data-layout]");
  if (layout) { S.layout = layout.dataset.layout; local.set("layout", S.layout); render(); return; }
  const filter = node.closest("[data-rf]");
  if (filter) { S.reviewFilter = filter.dataset.rf; render(); return; }
  const shot = node.closest("[data-shot]");
  if (shot && shot.dataset.shot && !node.closest("a") && !node.closest("video")) go(shotHref(shot.dataset.shot));
}

function shotHref(id) {
  const route = parseRoute(location.hash);
  const qs = location.hash.includes("?") ? `?${location.hash.split("?")[1]}` : "";
  return `#/${route.ep}/board/${id}${qs}`;
}

function onKey(event) {
  const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || "");
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); openPalette(); return; }
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") { if (S.edit) { event.preventDefault(); save(); } return; }
  if (event.key === "Escape") {
    if (!$("#palette").hidden) { closePalette(); return; }
    if (!$("#inspector").hidden) { go($("#inspector").dataset.back); return; }
  }
  if (event.key === "/" && !typing && $("#palette").hidden) { event.preventDefault(); openPalette(); return; }
  const route = parseRoute(location.hash);
  if (route.view === "board" && route.arg && !typing && $("#palette").hidden && ["ArrowRight", "ArrowLeft", "j", "k"].includes(event.key)) {
    const E = S.episodes.get(route.ep);
    const shots = E?.board?.shots || [];
    const index = shots.findIndex((shot) => shot.id === route.arg);
    const next = shots[index + (event.key === "ArrowRight" || event.key === "j" ? 1 : -1)];
    if (next) go(shotHref(next.id));
  }
  if (event.key === "Enter" && event.target.classList?.contains("shot")) event.target.click();
}

function onHover(event) {
  const node = event.target.closest?.("[data-tip]");
  const tip = $("#tip");
  if (!node) { tip.hidden = true; return; }
  tip.replaceChildren();
  if (node.dataset.tipB) tip.append(element("b", "", node.dataset.tipB));
  tip.append(document.createTextNode(node.dataset.tip));
  tip.hidden = false;
  const box = node.getBoundingClientRect();
  tip.style.left = `${Math.min(innerWidth - tip.offsetWidth - 8, Math.max(8, box.left + box.width / 2 - tip.offsetWidth / 2))}px`;
  tip.style.top = `${Math.max(8, box.top - tip.offsetHeight - 8)}px`;
}

function onHashChange() {
  if (S.edit?.dirty && !confirm("当前修改还没有保存，确认离开吗？")) {
    history.replaceState(null, "", S.lastHash);
    return;
  }
  S.lastHash = location.hash;
  render();
}

async function selectProject(id) {
  if (S.edit?.dirty && !confirm("当前修改还没有保存，确认离开吗？")) { render(); return; }
  S.edit = null;
  $("#view").dataset.state = "loading";
  try {
    await loadProject(id);
    S.status = await api(`/api/status?${query({ project: id })}`).catch(() => null);
    if (location.hash !== "#/") { S.lastHash = "#/"; history.replaceState(null, "", "#/"); }
    render();
  } catch (error) {
    showError(friendlyFailure(error.message));
  }
}

async function boot() {
  applyTheme();
  try {
    await establishSession();
    const data = await api("/api/projects");
    if (!data || !Array.isArray(data.projects)) throw new Error("invalid dashboard response");
    S.projects = data.projects;
    if (!S.projects.length) { $("#topbar").innerHTML = '<a class="zs-mark" href="#/" aria-label="短剧创作台">场</a>'; showError("还没有发现可打开的短剧项目。"); return; }
    const remembered = local.get("project", null);
    const id = S.projects.some((project) => project.id === remembered) ? remembered : S.projects[0].id;
    await loadProject(id);
    S.status = await api(`/api/status?${query({ project: id })}`).catch(() => null);
    S.lastHash = location.hash;
    await render();
  } catch (error) {
    showError(friendlyFailure(error.message));
  }
}

/** Documents are written in the conversation, not here: reread them when the creator comes back to this tab. */
async function refreshOnReturn() {
  if (!S.project || parseRoute(location.hash).page === "edit") return;
  try { await refreshProject(); } catch (_error) { return; }
  render();
}

function start() {
  document.addEventListener("click", (event) => { onClick(event); });
  document.addEventListener("keydown", onKey);
  document.addEventListener("mouseover", onHover);
  document.addEventListener("change", (event) => { if (event.target.id === "projectSelect") selectProject(event.target.value); });
  addEventListener("hashchange", onHashChange);
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") refreshOnReturn(); });
  addEventListener("beforeunload", (event) => { if (S.edit?.dirty) { event.preventDefault(); event.returnValue = ""; } });
  if (typeof matchMedia === "function") matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { if (S.theme === "auto") renderTop(parseRoute(location.hash)); });
  boot();
}

if (hasDocument && typeof window !== "undefined" && !window.__DESK_NO_START__) start();
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    creatorEditable,
    creatorProjection,
    creatorSection,
    creatorStatus,
    creatorTitle,
    episodeName,
    fileLabel,
    formatBytes,
    friendlyFailure,
    friendlyKey,
    lineShot,
    lineShots,
    mediaKind,
    nextFor,
    parseRoute,
    readJsonLines,
    renderMarkdown,
    rhythmChecks,
    savedContentIsCurrent,
    seriesTodos,
    viewForPath,
    OWNER_SECTIONS,
    SECTION_ORDER,
  };
}
