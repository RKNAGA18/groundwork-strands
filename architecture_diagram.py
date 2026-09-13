# -*- coding: utf-8 -*-
"""
Groundwork Architecture Diagram
Run:  python architecture_diagram.py
Out:  architecture_diagram.png
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

FIG_W, FIG_H = 22, 14
fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
ax.set_xlim(0, FIG_W)
ax.set_ylim(0, FIG_H)
ax.axis("off")
fig.patch.set_facecolor("#0d1117")
ax.set_facecolor("#0d1117")

C = {
    "bg":          "#0d1117",
    "lane_user":   "#0d2137",
    "lane_fe":     "#0d1f2d",
    "lane_be":     "#111827",
    "lane_pipe":   "#12191f",
    "lane_store":  "#0d1f18",
    "box_user":    "#1d4ed8",
    "box_fe":      "#0ea5e9",
    "box_route":   "#6366f1",
    "box_pipe":    "#7c3aed",
    "box_drafter": "#8b5cf6",
    "box_verify":  "#ec4899",
    "box_store":   "#059669",
    "box_conf":    "#f59e0b",
    "text_hi":     "#f8fafc",
    "text_lo":     "#94a3b8",
    "text_label":  "#cbd5e1",
    "green":       "#22c55e",
    "yellow":      "#eab308",
    "red":         "#ef4444",
    "arrow":       "#475569",
    "arrow_hi":    "#38bdf8",
}

def swim_lane(ax, x, y, w, h, color, label, label_color="#64748b"):
    rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05",
                          linewidth=0, facecolor=color, alpha=0.55, zorder=1)
    ax.add_patch(rect)
    ax.text(x + 0.18, y + h / 2, label, fontsize=8, color=label_color,
            fontweight="bold", rotation=90, va="center", ha="center",
            fontfamily="monospace", zorder=2)

def box(ax, x, y, w, h, color, title, sub="", title_size=9, sub_size=7.2, alpha=1.0, zorder=5):
    rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.12",
                          linewidth=1.2, edgecolor=color, facecolor=color,
                          alpha=alpha * 0.18, zorder=zorder)
    ax.add_patch(rect)
    rect2 = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.12",
                           linewidth=1.2, edgecolor=color, facecolor="none", zorder=zorder + 1)
    ax.add_patch(rect2)
    cy = y + h / 2 + (0.12 if sub else 0)
    ax.text(x + w / 2, cy, title, fontsize=title_size, color=C["text_hi"],
            fontweight="bold", va="center", ha="center", zorder=zorder + 2)
    if sub:
        ax.text(x + w / 2, y + h / 2 - 0.22, sub, fontsize=sub_size,
                color=C["text_lo"], va="center", ha="center",
                zorder=zorder + 2, fontfamily="monospace")

def arrow(ax, x1, y1, x2, y2, color="#475569", lw=1.5, label="", zorder=8):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(arrowstyle="->", color=color, lw=lw,
                        connectionstyle="arc3,rad=0.0"), zorder=zorder)
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx + 0.08, my + 0.08, label, fontsize=6.5, color=color, va="center", zorder=zorder + 1)

def badge(ax, x, y, n, color):
    circ = plt.Circle((x, y), 0.22, color=color, zorder=10)
    ax.add_patch(circ)
    ax.text(x, y, str(n), fontsize=7.5, color="white", fontweight="bold",
            va="center", ha="center", zorder=11)

# -- swim lanes --------------------------------------------------------------
swim_lane(ax, 0.4, 12.4, FIG_W - 0.8, 1.3,  C["lane_user"],  "USER",     "#60a5fa")
swim_lane(ax, 0.4, 10.6, FIG_W - 0.8, 1.6,  C["lane_fe"],    "FRONTEND", "#38bdf8")
swim_lane(ax, 0.4,  8.5, FIG_W - 0.8, 1.9,  C["lane_be"],    "BACKEND",  "#818cf8")
swim_lane(ax, 0.4,  3.8, FIG_W - 0.8, 4.5,  C["lane_pipe"],  "PIPELINE", "#c084fc")
swim_lane(ax, 0.4,  1.0, FIG_W - 0.8, 2.6,  C["lane_store"], "STORAGE",  "#34d399")

# -- title --------------------------------------------------------------------
ax.text(FIG_W / 2, 13.82, "GROUNDWORK  -  Security Questionnaire AI Agent",
        fontsize=16, color=C["text_hi"], fontweight="bold", va="center", ha="center")
ax.text(FIG_W / 2, 13.45,
        "Two independent agents  ?  one drafts  ?  one audits  ?  AWS Strands SDK  ?  BM25 Retrieval",
        fontsize=9, color=C["text_lo"], va="center", ha="center")

# -- USER layer ---------------------------------------------------------------
box(ax,  1.1, 12.5, 2.4, 0.95, C["box_user"], "Upload KB Docs",       ".md / .pdf / .txt")
box(ax,  4.2, 12.5, 2.4, 0.95, C["box_user"], "Upload Questionnaire", ".xlsx / .pdf")
box(ax, 14.5, 12.5, 2.8, 0.95, C["box_user"], "Review Answers",       "Green / Yellow / Red")
box(ax, 18.0, 12.5, 2.8, 0.95, C["box_user"], "Export .docx",         "human_approved only")

# -- FRONTEND layer -----------------------------------------------------------
box(ax,  1.1, 10.75, 5.6, 1.1, C["box_fe"], "Next.js 14 (App Router)",
    "frontend/app/page.tsx  - 3 tabs: Audit ? Ablation ? KB")
box(ax,  7.5, 10.75, 4.5, 1.1, C["box_fe"], "Interactive Verifier",
    "POST /api/verify-single  ?  live result")
box(ax, 13.2, 10.75, 5.6, 1.1, C["box_fe"], "Polling & Results Renderer",
    "GET /api/runs/{id}/status  +  /results")

# -- BACKEND ROUTES -----------------------------------------------------------
RY, RH = 8.65, 1.25
box(ax,  1.1, RY, 2.6, RH, C["box_route"], "POST /api/kb/upload",          "routes/kb.py")
box(ax,  4.1, RY, 3.1, RH, C["box_route"], "POST /api/questionnaire",      "routes/questionnaire.py")
box(ax,  7.6, RY, 2.9, RH, C["box_route"], "POST /api/runs/{id}/process",  "routes/runs.py")
box(ax, 10.9, RY, 2.6, RH, C["box_route"], "GET /status ? /results",       "routes/runs.py")
box(ax, 13.9, RY, 2.6, RH, C["box_route"], "PATCH /answers/{qid}",         "human approval")
box(ax, 16.9, RY, 2.9, RH, C["box_route"], "POST /export",                 "runs.py ? .docx")

# -- PIPELINE - 5 stages ------------------------------------------------------
PY, PH = 6.6, 1.4
sxs = [1.2,  4.2,  7.2, 11.5, 16.0]
sws = [2.4,  2.4,  3.5,  4.0,  3.6]
stages = [
    ("1  Parse",        "parse.py",              C["box_pipe"]),
    ("2  Retrieve",     "BM25Retriever",          C["box_pipe"]),
    ("3  DrafterAgent", "drafter.py / Strands",   C["box_drafter"]),
    ("4  VerifierAgent","verifier.py / Strands",  C["box_verify"]),
    ("5  Confidence",   "confidence.py",          C["box_conf"]),
]
for (sx, sw, (lbl, sub, col)) in zip(sxs, sws, stages):
    box(ax, sx, PY, sw, PH, col, lbl, sub, title_size=9.5)

# stage pipeline arrows
for i in range(len(sxs) - 1):
    x1 = sxs[i] + sws[i]
    x2 = sxs[i + 1]
    arrow(ax, x1, PY + PH / 2, x2, PY + PH / 2, C["arrow_hi"], lw=2.2)

# -- orchestrator bar ---------------------------------------------------------
box(ax, 1.2, 4.05, 18.4, 0.9, "#374151",
    "graph.py - Orchestrator  (ThreadPoolExecutor max_workers=5)   ?   force_red_if_no_real_evidence()   ?   graceful degradation",
    title_size=8, alpha=0.7)

# -- Strands agent detail boxes ------------------------------------------------
box(ax, 7.2,  4.3, 3.8, 1.35, C["box_drafter"],
    "DrafterAgent.invoke()", "@tool: retrieve_evidence, draft_answer", title_size=8, sub_size=7)
box(ax, 11.5, 4.3, 3.8, 1.35, C["box_verify"],
    "VerifierAgent.invoke()", "@tool: check_claim_against_sources", title_size=8, sub_size=7)
box(ax, 15.5, 4.8, 3.8, 0.85, "#f97316",
    "LLM (Groq / Bedrock)", "T=0.2 draft  ?  T=0.0 verify", title_size=8, sub_size=7)

# two-agent independence callout
box(ax, 7.15, 7.9, 8.4, 0.55, "#ec4899",
    "Two separate Agent instances ? two separate context windows ? Verifier never sees Drafter reasoning",
    title_size=7.5, alpha=0.6)

# drafter ? LLM, verifier ? LLM
arrow(ax, 11.1, 5.0, 15.5, 5.3, "#f97316", lw=1.5, label="invoke")
arrow(ax, 15.3, 5.05, 15.5, 5.15, "#f97316", lw=1.5)

# -- STORAGE layer ------------------------------------------------------------
box(ax,  1.2, 1.1, 4.5, 2.2, C["box_store"],
    "VectorStoreManager",
    "vector_store.py\nBM25Retriever (k1=1.5, b=0.75)\nthreshold=4.3  ?  top_k=5")
box(ax,  6.2, 1.1, 4.5, 2.2, C["box_store"],
    "RunStore",
    "run_store.py\nIn-memory dict keyed by run_id\nstatus ? progress ? results")
box(ax, 11.2, 1.1, 4.5, 2.2, C["box_store"],
    "Chunker",
    "storage/chunker.py\n500-word window, 50-word overlap\ndoc_id ? chunk_id ? doc_name")
box(ax, 16.2, 1.1, 4.5, 2.2, C["box_store"],
    "Disk  (uploads/)",
    "backend/uploads/\nAbsolute path via __file__\nAuto-created on boot")

# -- arrows -------------------------------------------------------------------
# user ? frontend
for ux, fx in [(2.3, 2.3), (5.4, 5.4)]:
    arrow(ax, ux, 12.5, fx, 11.85, C["arrow_hi"], lw=1.8)
arrow(ax, 15.9, 12.5, 15.9, 11.85, C["arrow_hi"], lw=1.8)
arrow(ax, 19.4, 12.5, 19.4, 11.85, C["arrow_hi"], lw=1.8)

# frontend ? routes
for cx in [2.3, 5.6, 9.0]:
    arrow(ax, cx, 10.75, cx, 9.9, C["arrow_hi"], lw=1.8)
arrow(ax, 14.5, 10.75, 14.5, 9.9, C["arrow_hi"], lw=1.8)

# process ? pipeline
arrow(ax, 9.0, 8.65, 9.0, 8.0, C["arrow_hi"], lw=2.2, label="background task")

# pipeline ? storage
arrow(ax, 3.2, PY, 3.4, 3.3, C["box_store"], lw=1.5, label="BM25 query")
arrow(ax, 9.0, PY, 9.0, 3.3, C["box_store"], lw=1.5, label="store chunks")
arrow(ax, 14.5, 4.05, 8.5, 3.3, C["box_store"], lw=1.2, label="persist results")

# storage internal links
for x1, x2 in [(5.7, 6.2), (10.7, 11.2), (15.7, 16.2)]:
    arrow(ax, x1, 2.2, x2, 2.2, C["box_store"], lw=1.3)

# -- Confidence legend ---------------------------------------------------------
lx, ly = 17.8, 1.1
ax.text(lx, ly + 2.12, "Confidence Status", fontsize=8, color=C["text_label"],
        fontweight="bold")
for i, (col, lbl) in enumerate([
    (C["green"],  "GREEN   - grounded, score >= 4.3"),
    (C["yellow"], "YELLOW  - partial / marginal match"),
    (C["red"],    "RED     - no evidence / unsupported"),
]):
    ry = ly + 1.65 - i * 0.52
    ax.add_patch(plt.Circle((lx + 0.18, ry), 0.14, color=col, zorder=10))
    ax.text(lx + 0.42, ry, lbl, fontsize=7, color=C["text_lo"], va="center")

ax.text(lx, ly + 0.1,
        "force_red() fires BEFORE Verifier LLM\n"
        "saves cost, blocks hallucination laundering",
        fontsize=6.5, color="#f97316", fontstyle="italic")

# -- footer -------------------------------------------------------------------
ax.text(FIG_W / 2, 0.25,
        "github.com/RKNAGA18/groundwork-strands  ?  MIT License  ?  AWS Agents for Humans Hackathon 2026",
        fontsize=7, color="#334155", ha="center")

fig.savefig("architecture_diagram.png", dpi=180, bbox_inches="tight",
            facecolor=fig.get_facecolor())
print("Saved -> architecture_diagram.png")