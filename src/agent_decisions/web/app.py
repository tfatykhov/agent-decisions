"""
Flask application for the agent-decisions web dashboard.
"""

from __future__ import annotations

import base64
import os
from datetime import datetime
from typing import TYPE_CHECKING

from flask import Flask, flash, redirect, render_template, request, url_for

if TYPE_CHECKING:
    pass


def create_app(journal_path: str = "./decisions") -> Flask:
    """
    Create and configure the Flask application.

    Args:
        journal_path: Path to the decisions directory

    Returns:
        Configured Flask app
    """
    from ..journal import Journal
    from ..models import Outcome

    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    # Load secret key from environment or generate a random one
    app.secret_key = os.environ.get("DECIDE_SECRET_KEY", os.urandom(32))

    # Initialize journal
    journal = Journal(journal_path)

    @app.route("/")
    def index() -> str:
        """Dashboard home with stats and recent decisions."""
        stats = journal.stats()
        decisions = sorted(
            journal.list_all(),
            key=lambda d: d.timestamp,
            reverse=True,
        )[:10]
        due = journal.list_due()

        return render_template(
            "index.html",
            stats=stats,
            decisions=decisions,
            due_count=len(due),
        )

    @app.route("/decisions")
    def decision_list() -> str:
        """List all decisions with filters."""
        filter_type = request.args.get("filter", "all")
        category = request.args.get("category")

        if filter_type == "pending":
            decisions = journal.list_pending()
        elif filter_type == "due":
            decisions = journal.list_due()
        elif category:
            decisions = journal.list_by_category(category)
        else:
            decisions = journal.list_all()

        # Sort by timestamp, newest first
        decisions = sorted(decisions, key=lambda d: d.timestamp, reverse=True)

        # Get unique categories for filter dropdown
        all_decisions = journal.list_all()
        categories = sorted(set(d.category for d in all_decisions))

        return render_template(
            "decisions.html",
            decisions=decisions,
            categories=categories,
            current_filter=filter_type,
            current_category=category,
        )

    @app.route("/decisions/<decision_id>")
    def decision_detail(decision_id: str) -> str:
        """Show details of a specific decision."""
        decision = journal.get(decision_id)
        if not decision:
            flash(f"Decision '{decision_id}' not found", "error")
            return redirect(url_for("decision_list"))

        return render_template("decision_detail.html", decision=decision)

    @app.route("/decisions/<decision_id>/review", methods=["POST"])
    def review_decision(decision_id: str) -> str:
        """Record the outcome of a decision."""
        from flask import g

        # CSRF protection: verify token
        csrf_token = request.form.get("csrf_token")
        expected_token = getattr(g, "csrf_token", None)
        if not csrf_token or not expected_token or csrf_token != expected_token:
            flash("Invalid request (CSRF check failed)", "error")
            return redirect(url_for("decision_detail", decision_id=decision_id))

        outcome = request.form.get("outcome")
        result = request.form.get("result", "")
        lessons = request.form.get("lessons", "")

        if not outcome:
            flash("Outcome is required", "error")
            return redirect(url_for("decision_detail", decision_id=decision_id))

        # Validate outcome enum
        valid_outcomes = {"success", "failure", "partial", "inconclusive"}
        if outcome not in valid_outcomes:
            flash(f"Invalid outcome: {outcome}", "error")
            return redirect(url_for("decision_detail", decision_id=decision_id))

        try:
            decision = journal.review(
                decision_id=decision_id,
                outcome=Outcome(outcome),
                actual_result=result or None,
                lessons=lessons or None,
            )

            if decision:
                flash(f"Decision reviewed: {outcome}", "success")
            else:
                flash(f"Decision '{decision_id}' not found", "error")
        except ValueError as e:
            flash(f"Error reviewing decision: {e}", "error")

        return redirect(url_for("decision_detail", decision_id=decision_id))

    @app.route("/plots")
    def plots_page() -> str:
        """Show calibration plots."""
        plot_type = request.args.get("type", "dashboard")

        # Check if matplotlib is available
        try:
            from .. import plots
        except ImportError:
            return render_template(
                "plots.html",
                error="matplotlib not installed. Install with: pip install agent-decisions[plots]",
                plot_type=plot_type,
            )

        decisions = journal.list_all()

        if not decisions:
            return render_template(
                "plots.html",
                error="No decisions found. Log some decisions first!",
                plot_type=plot_type,
            )

        # Generate the requested plot
        try:
            if plot_type == "calibration":
                img_bytes = plots.plot_calibration(decisions)
            elif plot_type == "brier":
                img_bytes = plots.plot_brier_over_time(decisions)
            elif plot_type == "confidence":
                img_bytes = plots.plot_confidence_distribution(decisions)
            elif plot_type == "reasons":
                img_bytes = plots.plot_reason_effectiveness(decisions)
            else:  # dashboard
                img_bytes = plots.plot_dashboard(decisions)

            if img_bytes:
                # Encode as base64 for inline display
                img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                return render_template(
                    "plots.html",
                    plot_data=img_b64,
                    plot_type=plot_type,
                )
            else:
                return render_template(
                    "plots.html",
                    error="Not enough data to generate this plot.",
                    plot_type=plot_type,
                )

        except Exception as e:
            return render_template(
                "plots.html",
                error=f"Error generating plot: {e}",
                plot_type=plot_type,
            )

    @app.route("/stats")
    def stats_page() -> str:
        """Show detailed statistics."""
        stats = journal.stats()
        decisions = journal.list_all()

        # Calculate additional stats
        reviewed = [d for d in decisions if not d.is_pending]

        # Reason type breakdown
        reason_counts: dict[str, int] = {}
        for d in decisions:
            for r in d.reasons:
                rtype = r.reason_type.value
                reason_counts[rtype] = reason_counts.get(rtype, 0) + 1

        return render_template(
            "stats.html",
            stats=stats,
            total_decisions=len(decisions),
            reviewed_count=len(reviewed),
            reason_counts=reason_counts,
        )

    @app.template_filter("datefmt")
    def datefmt_filter(dt: datetime, fmt: str = "%Y-%m-%d %H:%M") -> str:
        """Format a datetime for display."""
        if dt is None:
            return ""
        return dt.strftime(fmt)

    @app.template_filter("pct")
    def pct_filter(value: float | None) -> str:
        """Format a float as percentage."""
        if value is None:
            return "—"
        return f"{value:.0%}"

    @app.before_request
    def ensure_csrf_token():
        """Ensure CSRF token exists before processing request."""
        import secrets
        if "csrf_token" not in request.cookies:
            # Store token in g for this request, will be set as cookie in after_request
            from flask import g
            g.csrf_token = secrets.token_hex(32)
        else:
            from flask import g
            g.csrf_token = request.cookies.get("csrf_token")

    @app.after_request
    def set_csrf_cookie(response):
        """Set CSRF token cookie if not present."""
        from flask import g
        if "csrf_token" not in request.cookies and hasattr(g, "csrf_token"):
            response.set_cookie(
                "csrf_token",
                g.csrf_token,
                httponly=True,
                samesite="Strict",
                secure=request.is_secure,
            )
        return response

    @app.context_processor
    def inject_csrf_token():
        """Make CSRF token available in all templates."""
        from flask import g
        return {"csrf_token": getattr(g, "csrf_token", "")}

    return app


def run_server(
    journal_path: str = "./decisions",
    host: str = "127.0.0.1",
    port: int = 5000,
    debug: bool = False,
) -> None:
    """
    Run the web dashboard server.

    Args:
        journal_path: Path to the decisions directory
        host: Host to bind to
        port: Port to bind to
        debug: Enable debug mode
    """
    app = create_app(journal_path)
    app.run(host=host, port=port, debug=debug)
