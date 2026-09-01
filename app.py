import json
import os

import pandas as pd
import streamlit as st

from src.analyzer import classify_comment
from src.backlog import route_audience_need
from src.clustering import group_similar_comments
from src.exporters import backlog_to_csv, backlog_to_markdown
from src.scoring import demand_breakdown
from src.youtube import YouTubeAPIError, fetch_youtube_video


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
        min-height: 135px;
    }
    .mini-card .eyebrow {
        font-size: .78rem;
        opacity: .65;
        text-transform: uppercase;
        letter-spacing: .06em;
        margin-bottom: .35rem;
    }
    .mini-card .big { font-size: 1.25rem; font-weight: 700; line-height: 1.18; }
    .mini-card .sub { margin-top: .45rem; opacity: .72; font-size: .9rem; }
    .route-pill {
        display: inline-block;
        border: 1px solid rgba(120,120,120,.35);
        border-radius: 999px;
        padding: .18rem .55rem;
        font-size: .76rem;
        margin-right: .35rem;
        opacity: .9;
    }
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

for key, default in (
    ("manual_ai_plans", {}),
    ("youtube_df", None),
    ("youtube_meta", None),
    ("youtube_url", ""),
):
    if key not in st.session_state:
        st.session_state[key] = default


def get_youtube_api_key() -> str | None:
    env_key = os.getenv("YOUTUBE_API_KEY")
    if env_key:
        return env_key

    try:
        return st.secrets["YOUTUBE_API_KEY"]
    except (FileNotFoundError, KeyError):
        return None


@st.cache_data(ttl=900, show_spinner=False)
def cached_youtube_fetch(
    video_url: str,
    api_key: str,
    max_comments: int,
    sampling: str,
):
    return fetch_youtube_video(
        video_url,
        api_key,
        max_comments=max_comments,
        sampling=sampling,
    )


st.markdown(
    """
    <div class="hero">
      <h1>CommentOps</h1>
      <p><strong>Your audience already wrote your roadmap. We find it.</strong></p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("### Analyze a YouTube audience")
youtube_url = st.text_input(
    "YouTube video URL",
    placeholder="https://www.youtube.com/watch?v=...",
    label_visibility="collapsed",
)

c1, c2, c3 = st.columns([1, 1.25, 1])
with c1:
    max_comments = st.selectbox(
        "Comments",
        options=[100, 300, 500],
        index=1,
        help="Maximum number of unique top-level comments to analyze.",
    )
with c2:
    sampling_label = st.radio(
        "Sampling",
        options=["Balanced", "Top", "Latest"],
        horizontal=True,
        help="Balanced mixes YouTube relevance with recent comments and removes duplicates.",
    )
with c3:
    st.write("")
    st.write("")
    analyze_youtube = st.button(
        "Analyze audience →",
        type="primary",
        use_container_width=True,
    )

youtube_key = get_youtube_api_key()

if analyze_youtube:
    if not youtube_url.strip():
        st.error("Paste a YouTube video URL first.")
    elif not youtube_key:
        st.error(
            "YouTube live analysis is not configured yet. "
            "Set YOUTUBE_API_KEY locally or in Streamlit Secrets."
        )
    else:
        try:
            with st.spinner("Reading the public YouTube conversation..."):
                yt_df, yt_meta = cached_youtube_fetch(
                    youtube_url.strip(),
                    youtube_key,
                    max_comments,
                    sampling_label.lower(),
                )
            st.session_state.youtube_df = yt_df
            st.session_state.youtube_meta = yt_meta
            st.session_state.youtube_url = youtube_url.strip()
            st.session_state.manual_ai_plans = {}
        except (ValueError, YouTubeAPIError) as exc:
            st.error(str(exc))

with st.expander("Or upload a CSV"):
    uploaded = st.file_uploader(
        "Upload comment export",
        type=["csv"],
        help="Expected comment/text column. Likes are optional.",
    )

with st.sidebar:
    st.header("Analysis settings")
    creator_context = st.text_area(
        "Channel context (optional)",
        placeholder="Example: Python tutorials for beginner developers",
        height=90,
    )

    st.divider()
    st.caption("AI enhancement")
    st.success("Human-reviewed AI bridge")
    st.caption("Action plans can be imported from ChatGPT.")

    st.divider()
    minutes_per_reply = st.slider(
        "Estimated minutes per manual reply",
        min_value=1.0,
        max_value=5.0,
        value=2.5,
        step=0.5,
        help="Used only for the time-saved estimate.",
    )

    if st.session_state.youtube_df is not None:
        if st.button("Return to demo dataset", use_container_width=True):
            st.session_state.youtube_df = None
            st.session_state.youtube_meta = None
            st.session_state.youtube_url = ""
            st.session_state.manual_ai_plans = {}
            st.rerun()

source_label = "Synthetic demo"

if st.session_state.youtube_df is not None:
    df = st.session_state.youtube_df.copy()
    meta = st.session_state.youtube_meta
    source_label = "Live YouTube"

    st.success(
        f'Live YouTube · "{meta.title}" · {meta.channel_title} · '
        f'{len(df)} public top-level comments loaded'
    )

    metadata_cols = st.columns(3)
    metadata_cols[0].metric("Loaded comments", len(df))
    metadata_cols[1].metric(
        "Public comments on video",
        meta.public_comment_count if meta.public_comment_count is not None else "—",
    )
    metadata_cols[2].metric("Sampling", sampling_label)

elif uploaded is not None:
    df = pd.read_csv(uploaded)
    source_label = "CSV upload"
    st.session_state.manual_ai_plans = {}
    st.info("Using your uploaded CSV.")

else:
    df = pd.read_csv("data/demo_comments_120.csv")
    st.info(
        "Synthetic demo · 120 comments. "
        "Paste a YouTube URL above to analyze a real public conversation."
    )

if df.empty:
    st.warning("No comments were available for analysis.")
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
published_col = next(
    (lower_cols[k] for k in ("published_at", "published", "created_at", "timestamp") if k in lower_cols),
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
backlog = []

if not actionable.empty:
    for cluster_id, group in actionable.groupby("cluster_id"):
        avg_priority = float(group["priority"].mean())
        total_likes = int(group["likes"].sum())
        members = group["comment"].tolist()

        dates = group[published_col].tolist() if published_col and published_col in group else None
        score_parts = demand_breakdown(
            len(group),
            total_likes,
            avg_priority,
            dates,
        )

        representative = group.sort_values(
            ["priority", "likes"], ascending=False
        ).iloc[0]["comment"]

        route = route_audience_need(
            members,
            avg_priority=avg_priority,
            cluster_size=len(group),
            demand_score=score_parts.score,
        )

        cluster_members[int(cluster_id)] = members

        cluster = {
            "cluster_id": int(cluster_id),
            "representative": representative,
            "count": len(group),
            "likes": total_likes,
            "avg_priority": round(avg_priority, 1),
            "demand_score": score_parts.score,
            "score_parts": score_parts,
            "work_type": route.work_type,
            "priority_band": route.priority_band,
            "recommended_action": route.action,
            "route_rationale": route.rationale,
        }
        clusters.append(cluster)

        backlog.append(
            {
                "priority": route.priority_band,
                "type": route.work_type,
                "need": representative,
                "demand_score": score_parts.score,
                "comments": len(group),
                "likes": total_likes,
                "recommended_action": route.action,
                "rationale": route.rationale,
            }
        )

cluster_df = pd.DataFrame(
    [{k: v for k, v in item.items() if k != "score_parts"} for item in clusters]
)

if not cluster_df.empty:
    priority_sort = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    cluster_df["_priority_sort"] = cluster_df["priority_band"].map(priority_sort).fillna(9)
    cluster_df = cluster_df.sort_values(
        ["_priority_sort", "demand_score", "likes"],
        ascending=[True, False, False],
    ).drop(columns=["_priority_sort"])

cluster_lookup = {item["cluster_id"]: item for item in clusters}

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
    f"{source_label}. Estimate assumes {minutes_per_reply:g} minutes per manual reply. "
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
                  <div class="eyebrow">{row["priority_band"]} · {row["work_type"]} · Demand {row["demand_score"]}/100</div>
                  <div class="big">{title}</div>
                  <div class="sub">{row["count"]} comments · {row["likes"]} combined likes</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

st.divider()
tab_queue, tab_needs, tab_backlog, tab_method = st.tabs(
    ["Action queue", "Audience needs", "Creator backlog", "Methodology"]
)

with tab_queue:
    display_columns = ["comment", "category", "priority", "likes", "reason"]
    for optional in ("published_at", "reply_count"):
        if optional in df.columns:
            display_columns.append(optional)

    queue = df.sort_values(["priority", "likes"], ascending=False)[display_columns]
    st.dataframe(queue, use_container_width=True, hide_index=True)

    csv = queue.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download prioritized inbox",
        data=csv,
        file_name="commentops_prioritized_inbox.csv",
        mime="text/csv",
    )

with tab_needs:
    if cluster_df.empty:
        st.write("No recurring actionable audience needs detected.")
    else:
        prompt_clusters = []
        for _, row in cluster_df.head(8).iterrows():
            cid = int(row["cluster_id"])
            prompt_clusters.append(
                {
                    "cluster_id": cid,
                    "priority": row["priority_band"],
                    "work_type": row["work_type"],
                    "demand_score": int(row["demand_score"]),
                    "combined_likes": int(row["likes"]),
                    "comments": cluster_members[cid],
                }
            )

        prompt_payload = {
            "creator_context": creator_context.strip(),
            "source": source_label,
            "clusters": prompt_clusters,
        }

        prompt_text = f"""
You are the AI operations layer inside CommentOps, a tool for creators.

Analyze ONLY the audience comments supplied below.
For each cluster, produce one practical action plan grounded in the evidence.

Rules:
- Never invent facts about the creator, audience, product, bug resolution, or platform.
- Respect the work_type and priority supplied by CommentOps unless the evidence clearly contradicts them.
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

        with st.expander("ChatGPT bridge — optional AI enhancement"):
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
            cluster = cluster_lookup[cluster_id]
            parts = cluster["score_parts"]

            with st.expander(
                f'{row["priority_band"]} · {row["work_type"]} · '
                f'{row["demand_score"]}/100 · {row["count"]} comments · '
                f'{row["representative"][:75]}'
            ):
                top_left, top_mid, top_right = st.columns(3)
                top_left.metric("Demand", f'{row["demand_score"]}/100')
                top_mid.metric("Comments", row["count"])
                top_right.metric("Combined likes", row["likes"])

                st.markdown(
                    f'<span class="route-pill">{row["priority_band"]}</span>'
                    f'<span class="route-pill">{row["work_type"]}</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(f'**Recommended action:** {row["recommended_action"]}')
                st.caption(row["route_rationale"])

                st.markdown("#### Why this ranks here")
                s1, s2, s3, s4 = st.columns(4)

                with s1:
                    st.caption("Recurrence")
                    st.progress(parts.recurrence / parts.recurrence_max)
                    st.write(f"{parts.recurrence:g} / {parts.recurrence_max}")

                with s2:
                    st.caption("Engagement")
                    st.progress(parts.engagement / parts.engagement_max)
                    st.write(f"{parts.engagement:g} / {parts.engagement_max}")

                with s3:
                    st.caption("Urgency")
                    st.progress(parts.urgency / parts.urgency_max)
                    st.write(f"{parts.urgency:g} / {parts.urgency_max}")

                with s4:
                    st.caption("Freshness")
                    if parts.freshness is None:
                        st.write("N/A")
                        st.caption("No timestamps")
                    else:
                        st.progress(parts.freshness / parts.freshness_max)
                        st.write(f"{parts.freshness:g} / {parts.freshness_max}")

                if parts.freshness is None:
                    st.caption(
                        "Freshness unavailable: score is normalized across recurrence, engagement, and urgency only."
                    )

                st.markdown("#### Evidence from the audience")
                for comment in members[:10]:
                    st.write(f"• {comment}")

                if plan:
                    st.divider()
                    st.markdown("### AI action plan")
                    left, right = st.columns(2)

                    with left:
                        st.markdown("**What the audience needs**")
                        st.markdown(
                            f'<div class="plan-box">{plan.get("summary", "")}</div>',
                            unsafe_allow_html=True,
                        )
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

with tab_backlog:
    st.markdown("### Creator Backlog")
    st.caption(
        "Audience needs are routed into creator work. Operational failures are intentionally prioritized over content ideas."
    )

    if not backlog:
        st.info("No backlog items yet.")
    else:
        backlog_frame = pd.DataFrame(backlog)
        priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        backlog_frame["_sort"] = backlog_frame["priority"].map(priority_order).fillna(9)
        backlog_frame = backlog_frame.sort_values(
            ["_sort", "demand_score"],
            ascending=[True, False],
        ).drop(columns=["_sort"])

        type_filter = st.multiselect(
            "Filter work type",
            options=["Support", "Documentation", "Content", "Education", "Community"],
            default=[],
            placeholder="All work types",
        )

        visible_backlog = backlog_frame
        if type_filter:
            visible_backlog = backlog_frame[backlog_frame["type"].isin(type_filter)]

        st.dataframe(
            visible_backlog[
                [
                    "priority",
                    "type",
                    "need",
                    "demand_score",
                    "comments",
                    "likes",
                    "recommended_action",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

        csv_data = backlog_to_csv(backlog)
        md_data = backlog_to_markdown(backlog)

        dl1, dl2 = st.columns(2)
        with dl1:
            st.download_button(
                "Export backlog as CSV",
                data=csv_data,
                file_name="commentops_creator_backlog.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with dl2:
            st.download_button(
                "Export backlog as Markdown",
                data=md_data,
                file_name="commentops_creator_backlog.md",
                mime="text/markdown",
                use_container_width=True,
            )

with tab_method:
    st.markdown("### How CommentOps prioritizes audience needs")
    st.write(
        "CommentOps intentionally separates deterministic prioritization from optional generative AI."
    )

    st.markdown("**1. Triage**")
    st.write("Comments are classified into actionable, low-priority, and likely spam.")

    st.markdown("**2. Audience-need grouping**")
    st.write(
        "A conservative clustering stage prefers false splits over false merges so unrelated creator work is not collapsed together."
    )

    st.markdown("**3. Demand Score**")
    st.write(
        "Recurrence (35), engagement (25), urgency (25), and—when timestamps exist—freshness (15). "
        "Engagement uses logarithmic scaling and freshness uses a 45-day half-life rather than a hard cutoff."
    )

    st.markdown("**4. Work routing**")
    st.write(
        "Each recurring need becomes Support, Documentation, Content, Education, or Community work with a P0–P3 priority."
    )

    st.markdown("**5. Optional AI enhancement**")
    st.write(
        "Generative AI can draft replies, pinned comments, and content briefs, but the evidence and prioritization remain visible for human review."
    )

    st.info(
        "Demand Score is a prioritization heuristic, not a prediction of future views or creator revenue. "
        "The time-saved metric is an adjustable estimate."
    )
