import os
import json
from datetime import datetime, timezone
from collections import defaultdict
from github import Github, Auth


def week_label(dt):
    return dt.strftime("%Y-W%V")


def main():
    token = os.environ.get("GITHUB_TOKEN")
    repo_name = os.environ.get("GITHUB_REPOSITORY", "unb-mds/2026.1-ContraDito")

    metrics = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repository": repo_name,
        "issues_per_week": [],
        "commit_message_histogram": [],
        "coauthors_per_week": [],
        "commit_heatmap": [],
        "top_committers": [],
        "top_pr_authors": [],
        "top_issue_contributors": [],
        "pull_requests_time_to_merge": [],
        "code_review_matrix": [],
        "lead_time_issues_by_label": [],
        "code_churn_per_week": [],
        "commit_types_distribution": [],
        "velocity": [],
        "individual_stats": [],
        "commit_chars_per_week": [],
    }

    output_path = os.path.join(os.path.dirname(__file__), "..", "docs", "productivity", "metrics.json")

    if not token:
        print("GITHUB_TOKEN não encontrado. Gerando arquivo vazio para teste local.")
        with open(output_path, "w") as f:
            json.dump(metrics, f, indent=2)
        return

    print(f"Conectando ao repositório {repo_name}...")
    g = Github(auth=Auth.Token(token))
    repo = g.get_repo(repo_name)

    # ── 1. Commits ────────────────────────────────────────────────────────────
    print("Processando commits...")
    try:
        commits = repo.get_commits(sha="develop")
    except Exception as e:
        print(f"Branch 'develop' não encontrada, usando padrão: {e}")
        commits = repo.get_commits()

    commit_counts = defaultdict(int)
    commit_types = defaultdict(int)
    msg_lengths = {"0-20": 0, "21-50": 0, "51-100": 0, "101-200": 0, "200+": 0}
    heatmap = defaultdict(int)
    coauthors_weekly = defaultdict(int)
    churn_weekly = defaultdict(lambda: {"additions": 0, "deletions": 0, "modifications": 0})
    chars_weekly = defaultdict(lambda: {"total": 0, "count": 0})

    for i, commit in enumerate(commits):
        if i >= 300:
            break

        if commit.author:
            commit_counts[commit.author.login] += 1

        msg = commit.commit.message
        first_line = msg.split("\n")[0]
        fl_lower = first_line.lower()

        if fl_lower.startswith("feat"):
            commit_types["feat"] += 1
        elif fl_lower.startswith("fix"):
            commit_types["fix"] += 1
        elif fl_lower.startswith("docs"):
            commit_types["docs"] += 1
        elif fl_lower.startswith("chore"):
            commit_types["chore"] += 1
        elif fl_lower.startswith("refactor"):
            commit_types["refactor"] += 1
        elif fl_lower.startswith("test"):
            commit_types["test"] += 1
        else:
            commit_types["other"] += 1

        ln = len(first_line)
        if ln <= 20:
            msg_lengths["0-20"] += 1
        elif ln <= 50:
            msg_lengths["21-50"] += 1
        elif ln <= 100:
            msg_lengths["51-100"] += 1
        elif ln <= 200:
            msg_lengths["101-200"] += 1
        else:
            msg_lengths["200+"] += 1

        dt = commit.commit.author.date
        w = week_label(dt)
        heatmap[(dt.weekday(), dt.hour)] += 1
        coauthors_weekly[w] += msg.lower().count("co-authored-by:")
        chars_weekly[w]["total"] += ln
        chars_weekly[w]["count"] += 1

        # Code churn limited to first 50 commits (API rate constraint)
        if i < 50 and commit.stats:
            churn_weekly[w]["additions"] += commit.stats.additions
            churn_weekly[w]["deletions"] += commit.stats.deletions
            churn_weekly[w]["modifications"] += (
                commit.stats.total - commit.stats.additions - commit.stats.deletions
            )

    metrics["commit_message_histogram"] = [
        {"range": r, "count": c} for r, c in msg_lengths.items() if c > 0
    ]
    metrics["commit_heatmap"] = [
        {"day": d, "hour": h, "count": c} for (d, h), c in heatmap.items()
    ]
    metrics["coauthors_per_week"] = [
        {"week": w, "count": c} for w, c in sorted(coauthors_weekly.items())
    ]
    metrics["code_churn_per_week"] = [
        {"week": w, **data} for w, data in sorted(churn_weekly.items())
    ]
    metrics["top_committers"] = [
        {"username": u, "name": u, "commits": c}
        for u, c in sorted(commit_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    ]
    metrics["commit_types_distribution"] = [
        {"type": t, "count": c} for t, c in commit_types.items() if c > 0
    ]
    metrics["commit_chars_per_week"] = [
        {
            "week": w,
            "avg_chars": round(d["total"] / d["count"], 1),
            "total_commits": d["count"],
        }
        for w, d in sorted(chars_weekly.items())
        if d["count"] > 0
    ]

    # ── 2. Issues ─────────────────────────────────────────────────────────────
    print("Processando issues...")
    issues_by_week = defaultdict(lambda: {"opened": 0, "closed": 0})
    issue_contributors = defaultdict(lambda: {"opened": 0, "closed": 0, "total": 0})
    lead_time_by_label = defaultdict(list)

    for i, issue in enumerate(repo.get_issues(state="all")):
        if i >= 200:
            break
        if "/pull/" in issue.html_url:
            continue

        w = week_label(issue.created_at)
        issues_by_week[w]["opened"] += 1
        if issue.user:
            issue_contributors[issue.user.login]["opened"] += 1
            issue_contributors[issue.user.login]["total"] += 1

        if issue.state == "closed" and issue.closed_at:
            cw = week_label(issue.closed_at)
            issues_by_week[cw]["closed"] += 1
            if issue.closed_by:
                issue_contributors[issue.closed_by.login]["closed"] += 1
                issue_contributors[issue.closed_by.login]["total"] += 1

            days = (issue.closed_at - issue.created_at).total_seconds() / 86400.0
            for label in issue.labels:
                lead_time_by_label[label.name].append(days)

    sorted_issue_weeks = sorted(issues_by_week.keys())
    metrics["issues_per_week"] = [
        {"week": w, "opened": issues_by_week[w]["opened"], "closed": issues_by_week[w]["closed"]}
        for w in sorted_issue_weeks[-10:]
    ]
    metrics["top_issue_contributors"] = [
        {"username": u, "name": u, **{k: d[k] for k in ("opened", "closed", "total")}}
        for u, d in sorted(issue_contributors.items(), key=lambda x: x[1]["total"], reverse=True)[:10]
    ]
    metrics["lead_time_issues_by_label"] = [
        {"label": lbl, "avg_days_to_close": round(sum(times) / len(times), 1)}
        for lbl, times in lead_time_by_label.items()
        if times
    ]

    # Velocity: issues closed per week + 4-week rolling average
    velocity = []
    for i, w in enumerate(sorted_issue_weeks):
        closed = issues_by_week[w]["closed"]
        window = [
            issues_by_week[sorted_issue_weeks[j]]["closed"]
            for j in range(max(0, i - 3), i + 1)
        ]
        velocity.append({
            "week": w,
            "issues_closed": closed,
            "rolling_avg": round(sum(window) / len(window), 1),
        })
    metrics["velocity"] = velocity[-10:]

    # ── 3. Pull Requests & Reviews ────────────────────────────────────────────
    print("Processando PRs e reviews...")
    pr_authors = defaultdict(int)
    pr_merged_by = defaultdict(int)
    pr_merge_times_by_week = defaultdict(list)
    review_matrix = defaultdict(int)   # (reviewer, author) → approved count
    pr_reviewed_by = defaultdict(int)  # reviewer → reviews given

    for i, pr in enumerate(repo.get_pulls(state="all")):
        if i >= 100:
            break

        pr_author = pr.user.login if pr.user else "unknown"
        if pr.user:
            pr_authors[pr_author] += 1

        if pr.merged_at and pr.created_at:
            w = week_label(pr.merged_at)
            pr_merge_times_by_week[w].append(
                (pr.merged_at - pr.created_at).total_seconds() / 3600.0
            )
            if pr.merged_by:
                pr_merged_by[pr.merged_by.login] += 1

        try:
            for review in pr.get_reviews():
                if review.state == "APPROVED" and review.user:
                    reviewer = review.user.login
                    review_matrix[(reviewer, pr_author)] += 1
                    pr_reviewed_by[reviewer] += 1
        except Exception:
            pass

    metrics["top_pr_authors"] = [
        {"username": u, "name": u, "prs_opened": c}
        for u, c in sorted(pr_authors.items(), key=lambda x: x[1], reverse=True)[:10]
    ]
    metrics["pull_requests_time_to_merge"] = [
        {"week": w, "avg_hours": round(sum(times) / len(times), 1)}
        for w, times in sorted(pr_merge_times_by_week.items())[-10:]
        if times
    ]
    metrics["code_review_matrix"] = [
        {"reviewer": rev, "author": auth, "approved_prs": c}
        for (rev, auth), c in review_matrix.items()
    ]

    # ── 4. Individual Stats ───────────────────────────────────────────────────
    all_users = set(commit_counts) | set(pr_authors) | set(issue_contributors)
    metrics["individual_stats"] = sorted(
        [
            {
                "username": u,
                "name": u,
                "commits": commit_counts.get(u, 0),
                "prs_opened": pr_authors.get(u, 0),
                "prs_reviewed": pr_reviewed_by.get(u, 0),
                "prs_merged": pr_merged_by.get(u, 0),
                "issues_opened": issue_contributors[u]["opened"],
                "issues_closed": issue_contributors[u]["closed"],
            }
            for u in all_users
        ],
        key=lambda x: x["commits"],
        reverse=True,
    )

    with open(output_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Métricas salvas em {output_path}")


if __name__ == "__main__":
    main()
