import json

import pandas as pd
import streamlit as st

from src.analyzer import classify_comment
from src.clustering import group_similar_comments
from src.scoring import demand_score


st.set_page_config(page_title="CommentOps", page_icon="💬", layout="wide")

st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 4rem; }
    .hero {
        padding: 1.4rem 1.5rem;
        border: 1px solid rgba(120,120,120,.25);
        border-radius: 18px;
        margin-bottom: 1.2rem;
    }
    .hero h1 { margin: 0 0 .25rem 0; font-size: 2.5rem; }
    .hero p { margin: 0; opacity: .75; font-size: 1.05rem; }
    .mini-card {
        border: 1px solid rgba(120,120,120,.25);
        border-radius: 14px;
        padding: 1rem;
        min-height: 120px;
    }
    .mini-card .eyebrow {
        font-size: .78rem;
        opacity: .65;
        text-transform: uppercase;
        letter-spacing: .06em;
        margin-bottom: .35rem;
    }
    .mini-card .big { font-size: 1.35rem; font-weight: 700; line-height: 1.15; }
    .mini-card .sub { margin-top: .45rem; opacity: .72; font-size: .9rem; }
    .plan-box {
        border: 1px solid rgba(120,120,120,.25);
        border-radius: 14px;
        padding: 1rem 1.1rem;
        margin: .5rem 0 .85rem 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "manual_ai_plans" not in st.session_state:
    st.session_state.manual_ai_plans = {}

st.markdown(
    """
    <div class="hero">
      <h1>CommentOps</h1>
      <p>Turn audience noise into a prioritized creator action plan.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Input")
    uploaded = st.file_uploader("Upload a CSV", type=["csv"])
    st.caption("Expected: a comment/text column. Optional: likes.")

    st.divider()
    st.header("ChatGPT mode")
    creator_context = st.text_area(
        "Channel context (optional)",
        placeholder="Example: Python tutorials for beginner developers",
        height=90,
    )
    st.success("Zero-API mode")
    st.caption("No API key. No API charges.")

    st.divider()
    minutes_per_reply = st.slider(
        "Estimated minutes per manual reply",
        min_value=1.0,
        max_value=5.0,
        value=2.5,
        step=0.5,
        help="Used only for the time-saved estimate shown in the demo.",
    )

if uploaded:
    df = pd.read_csv(uploaded)
else:
    df = pd.read_csv("data/demo_comments.csv")
    st.info("Using the built-in demo dataset. Upload a CSV to analyze your own comments.")

if df.empty:
    st.warning("The dataset is empty.")
    st.stop()

lower_cols = {c.lower(): c for c in df.columns}
comment_col = next(
    (lower_cols[k] for k in ("comment", "text", "content", "message") if k in lower_cols),
    None,
)

if comment_col is None:
    st.error("No comment column found. Use one named: comment, text, content, or message.")
    st.stop()

likes_col = next(
    (lower_cols[k] for k in ("likes", "like_count", "votes") if k in lower_cols),
    None,
)

df = df.copy()
df["comment"] = df[comment_col].fillna("").astype(str)
df["likes"] = (
    pd.to_numeric(df[likes_col], errors="coerce").fillna(0).astype(int)
    if likes_col
    else 0
)

analysis = df["comment"].apply(classify_comment)
df[["category", "priority", "reason"]] = pd.DataFrame(
    analysis.tolist(), index=df.index
)

actionable = df[df["category"] == "reply_now"].copy()
actionable["cluster_id"] = group_similar_comments(actionable["comment"].tolist())

clusters = []
cluster_members = {}

if not actionable.empty:
    for cluster_id, group in actionable.groupby("cluster_id"):
        avg_priority = float(group["priority"].mean())
        total_likes = int(group["likes"].sum())
        score = demand_score(len(group), total_likes, avg_priority)
        members = group["comment"].tolist()
        cluster_members[int(cluster_id)] = members
        clusters.append(
            {
                "cluster_id": int(cluster_id),
                "representative": group.sort_values(
                    ["priority", "likes"], ascending=False
                ).iloc[0]["comment"],
                "count": len(group),
                "likes": total_likes,
                "avg_priority": round(avg_priority, 1),
                "demand_score": score,
            }
        )

cluster_df = pd.DataFrame(clusters)
if not cluster_df.empty:
    cluster_df = cluster_df.sort_values("demand_score", ascending=False)

actionable_count = int((df["category"] == "reply_now").sum())
topic_count = len(cluster_df)
duplicate_replies_avoided = max(actionable_count - topic_count, 0)
estimated_minutes_saved = duplicate_replies_avoided * minutes_per_reply

st.subheader("Creator Command Center")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Comments scanned", len(df))
m2.metric("Needs attention", actionable_count)
m3.metric("Audience needs", topic_count)
m4.metric("Est. time saved", f"{estimated_minutes_saved:.0f} min")

st.caption(
    f"Estimate assumes {minutes_per_reply:g} minutes per manual reply. "
    f"CommentOps reduces {actionable_count} individual reply decisions to {topic_count} grouped needs."
)

if not cluster_df.empty:
    top = cluster_df.head(3).reset_index(drop=True)
    cards = st.columns(len(top))
    for col, (_, row) in zip(cards, top.iterrows()):
        cid = int(row["cluster_id"])
        plan = st.session_state.manual_ai_plans.get(cid)
        title = plan.get("title") if plan and plan.get("title") else row["representative"]
        with col:
            st.markdown(
                f"""
                <div class="mini-card">
                  <div class="eyebrow">Demand {row["demand_score"]}/100 · {row["count"]} comments</div>
                  <div class="big">{title}</div>
                  <div class="sub">{row["likes"]} combined likes</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

st.divider()
tab1, tab2 = st.tabs(["Action queue", "Reply once"])

with tab1:
    queue = df.sort_values(["priority", "likes"], ascending=False)[
        ["comment", "category", "priority", "likes", "reason"]
    ]
    st.dataframe(queue, use_container_width=True, hide_index=True)
    csv = queue.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download prioritized inbox",
        data=csv,
        file_name="commentops_prioritized_inbox.csv",
        mime="text/csv",
    )

with tab2:
    if cluster_df.empty:
        st.write("No recurring actionable topics detected.")
    else:
        prompt_clusters = []
        for _, row in cluster_df.head(6).iterrows():
            cid = int(row["cluster_id"])
            prompt_clusters.append(
                {
                    "cluster_id": cid,
                    "demand_score": int(row["demand_score"]),
                    "combined_likes": int(row["likes"]),
                    "comments": cluster_members[cid],
                }
            )

        prompt_payload = {
            "creator_context": creator_context.strip(),
            "clusters": prompt_clusters,
        }

        prompt_text = f"""
You are the AI operations layer inside CommentOps, a tool for creators.

Analyze ONLY the audience comments supplied below.
For each cluster, produce one practical action plan grounded in the evidence.

Rules:
- Never invent facts about the creator, audience, product, bug resolution, or platform.
- If there is not enough information to answer factually, say the creator should investigate or provide more details.
- Replies should sound natural, concise, and human.
- Content ideas must be directly supported by the recurring audience need.
- Return ONLY valid JSON. No markdown fences. No explanation.

Return this exact structure:
{{
  "plans": [
    {{
      "cluster_id": 0,
      "summary": "short summary",
      "intent": "question|bug_report|tutorial_request|confusion|feedback|other",
      "recommended_action": "what the creator should do",
      "reply": "draft reply",
      "pinned_comment": "draft pinned comment",
      "content_idea": "content opportunity",
      "title": "suggested content title",
      "hook": "opening hook"
    }}
  ]
}}

INPUT:
{json.dumps(prompt_payload, ensure_ascii=False, indent=2)}
""".strip()

        with st.expander("ChatGPT bridge — zero API cost"):
            st.write("Copy the prompt into ChatGPT, then paste the returned JSON below.")
            st.text_area("Prompt for ChatGPT", value=prompt_text, height=300)
            ai_json = st.text_area(
                "Paste ChatGPT JSON response",
                height=220,
                placeholder='{"plans":[...]}',
            )

            if st.button("Import AI action plans", type="primary"):
                try:
                    parsed = json.loads(ai_json)
                    plans = parsed.get("plans", [])
                    imported = 0
                    for plan in plans:
                        cid = int(plan["cluster_id"])
                        st.session_state.manual_ai_plans[cid] = plan
                        imported += 1
                    st.success(f"Imported {imported} AI action plans.")
                except Exception as exc:
                    st.error(f"Could not parse the JSON: {exc}")

        for _, row in cluster_df.iterrows():
            cluster_id = int(row["cluster_id"])
            members = cluster_members[cluster_id]
            plan = st.session_state.manual_ai_plans.get(cluster_id)

            with st.expander(
                f'{row["demand_score"]}/100 · {row["count"]} comments · {row["representative"][:90]}'
            ):
                info1, info2, info3 = st.columns(3)
                info1.metric("Demand", f'{row["demand_score"]}/100')
                info2.metric("Comments", row["count"])
                info3.metric("Combined likes", row["likes"])

                st.markdown("**Evidence from the audience**")
                for comment in members[:8]:
                    st.write(f"• {comment}")

                if plan:
                    st.divider()
                    st.markdown("### ChatGPT action plan")
                    left, right = st.columns(2)

                    with left:
                        st.markdown("**What the audience needs**")
                        st.markdown(
                            f'<div class="plan-box">{plan.get("summary", "")}</div>',
                            unsafe_allow_html=True,
                        )
                        st.markdown("**Intent**")
                        st.write(str(plan.get("intent", "")).replace("_", " ").title())
                        st.markdown("**Recommended action**")
                        st.markdown(
                            f'<div class="plan-box">{plan.get("recommended_action", "")}</div>',
                            unsafe_allow_html=True,
                        )
                        st.markdown("**Draft reply**")
                        st.text_area(
                            f"reply_{cluster_id}",
                            value=plan.get("reply", ""),
                            height=130,
                            label_visibility="collapsed",
                        )

                    with right:
                        st.markdown("**Pinned comment**")
                        st.text_area(
                            f"pinned_{cluster_id}",
                            value=plan.get("pinned_comment", ""),
                            height=130,
                            label_visibility="collapsed",
                        )
                        st.markdown("**Content opportunity**")
                        st.markdown(
                            f'<div class="plan-box">{plan.get("content_idea", "")}</div>',
                            unsafe_allow_html=True,
                        )
                        st.markdown("**Suggested title**")
                        st.markdown(
                            f'<div class="plan-box"><strong>{plan.get("title", "")}</strong></div>',
                            unsafe_allow_html=True,
                        )
                        st.markdown("**Hook**")
                        st.text_area(
                            f"hook_{cluster_id}",
                            value=plan.get("hook", ""),
                            height=110,
                            label_visibility="collapsed",
                        )
                else:
                    st.info(
                        "Import a ChatGPT action plan to generate the reply, pinned comment, and content opportunity."
                    )

        if st.session_state.manual_ai_plans:
            export_payload = {
                "generated_with": "ChatGPT bridge (zero API mode)",
                "plans": list(st.session_state.manual_ai_plans.values()),
            }
            st.download_button(
                "Download AI action plans",
                data=json.dumps(export_payload, ensure_ascii=False, indent=2),
                file_name="commentops_ai_action_plans.json",
                mime="application/json",
            )
