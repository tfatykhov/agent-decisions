"""
Command-line interface for agent-decisions.
"""

import re
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from .journal import Journal
from .models import MentalState, Outcome, ReasonType, Stakes

# Check if matplotlib is actually available (not just plots module)
PLOTS_AVAILABLE = False
try:
    import matplotlib  # noqa: F401

    from . import plots
    PLOTS_AVAILABLE = True
except ImportError:
    PLOTS_AVAILABLE = False

console = Console()


def parse_duration(value: str) -> int:
    """Parse duration string like '7d', '2w', '1m' into days."""
    match = re.match(r"(\d+)([dwm])", value.lower())
    if not match:
        raise click.BadParameter(f"Invalid duration: {value}. Use format like '7d', '2w', '1m'")

    num = int(match.group(1))
    unit = match.group(2)

    if unit == "d":
        return num
    elif unit == "w":
        return num * 7
    elif unit == "m":
        return num * 30

    return num


@click.group()
@click.option("--dir", "-d", "directory", default="./decisions", help="Decision journal directory")
@click.pass_context
def main(ctx: click.Context, directory: str) -> None:
    """Decision Black Box - Track and review your decisions."""
    ctx.ensure_object(dict)
    ctx.obj["journal"] = Journal(directory)


@main.command()
@click.argument("summary")
@click.option("--confidence", "-c", type=float, required=True, help="Confidence (0.0-1.0)")
@click.option("--category", "-t", default="general", help="Category/domain")
@click.option("--stakes", "-s", type=click.Choice(["low", "medium", "high", "critical"]), default="medium")
@click.option("--context", help="Additional context")
@click.option("--alternative", "-a", multiple=True, help="Alternative options considered")
@click.option("--review-in", "-r", help="Review in N days/weeks/months (e.g., '7d', '2w', '1m')")
@click.option("--active-context", "-k", multiple=True, help="Active context items (K-lines: tools, files, APIs)")
@click.option("--related", multiple=True, help="Related decision IDs or 'id:title:distance' format")
@click.option("--mental-state", "-m", type=click.Choice(["deliberate", "reactive", "exploratory", "habitual", "pressured"]), help="Mental state when deciding")
@click.option("--teaching-notes", help="Notes for future self")
@click.option("--reason", "-R", multiple=True, help="Reason supporting decision: 'type:text' or 'type:text:strength' (e.g., 'pattern:Similar to X which worked:0.8')")
@click.option("--query-run/--no-query-run", default=False, help="Pre-decision: queried similar decisions")
@click.option("--similar-found", type=int, default=0, help="Pre-decision: number of similar decisions found")
@click.option("--guardrails-checked/--no-guardrails-checked", default=False, help="Pre-decision: checked guardrails")
@click.option("--guardrails-passed/--no-guardrails-passed", default=False, help="Pre-decision: guardrails passed")
@click.pass_context
def log(
    ctx: click.Context,
    summary: str,
    confidence: float,
    category: str,
    stakes: str,
    context: Optional[str],
    alternative: tuple[str, ...],
    review_in: Optional[str],
    active_context: tuple[str, ...],
    related: tuple[str, ...],
    mental_state: Optional[str],
    teaching_notes: Optional[str],
    reason: tuple[str, ...],
    query_run: bool,
    similar_found: int,
    guardrails_checked: bool,
    guardrails_passed: bool,
) -> None:
    """Log a new decision."""
    from .models import PreDecisionProtocol, RelatedDecision
    
    journal: Journal = ctx.obj["journal"]

    # Parse reasons
    parsed_reasons = []
    for r in reason:
        parts = r.split(":", 2)
        if len(parts) >= 2:
            rtype = parts[0]
            rtext = parts[1]
            rstrength = float(parts[2]) if len(parts) > 2 else 0.5
            try:
                parsed_reasons.append({
                    "type": ReasonType(rtype),
                    "text": rtext,
                    "strength": rstrength,
                })
            except ValueError:
                valid_types = ", ".join([t.value for t in ReasonType])
                console.print(f"[yellow]Warning: Unknown reason type '{rtype}'. Valid: {valid_types}[/yellow]")

    # Parse related decisions (support both simple ID and id:title:distance format)
    parsed_related = []
    for rel in related:
        parts = rel.split(":", 2)
        if len(parts) == 3:
            # Format: id:title:distance
            parsed_related.append(RelatedDecision(id=parts[0], title=parts[1], distance=float(parts[2])))
        elif len(parts) == 2:
            # Format: id:title
            parsed_related.append(RelatedDecision(id=parts[0], title=parts[1]))
        else:
            # Just ID
            parsed_related.append(RelatedDecision(id=rel))

    # Build pre-decision protocol if any flags set
    pre_decision = None
    if query_run or guardrails_checked:
        pre_decision = PreDecisionProtocol(
            query_run=query_run,
            similar_found=similar_found,
            guardrails_checked=guardrails_checked,
            guardrails_passed=guardrails_passed,
        )

    review_days = parse_duration(review_in) if review_in else None

    decision = journal.log(
        summary=summary,
        confidence=confidence,
        category=category,
        stakes=Stakes(stakes),
        context=context,
        alternatives=list(alternative),
        review_days=review_days,
        active_context=list(active_context),
        related_decisions=parsed_related,
        mental_state=MentalState(mental_state) if mental_state else None,
        teaching_notes=teaching_notes,
        reasons=parsed_reasons,
        pre_decision_protocol=pre_decision,
    )

    console.print(f"[green]✓[/green] Decision logged: [bold]{decision.id}[/bold]")
    console.print(f"  Summary: {decision.summary}")
    console.print(f"  Confidence: {decision.confidence:.0%}")
    if pre_decision:
        console.print(f"  Pre-decision: query={'✅' if pre_decision.query_run else '❌'} guardrails={'✅' if pre_decision.guardrails_passed else '❌'}")
    if decision.review_date:
        console.print(f"  Review on: {decision.review_date.strftime('%Y-%m-%d')}")


@main.command("list")
@click.option("--pending", "-p", is_flag=True, help="Show only pending decisions")
@click.option("--due", is_flag=True, help="Show only decisions due for review")
@click.option("--category", "-t", help="Filter by category")
@click.option("--limit", "-n", type=int, default=20, help="Max number to show")
@click.pass_context
def list_decisions(
    ctx: click.Context,
    pending: bool,
    due: bool,
    category: Optional[str],
    limit: int,
) -> None:
    """List decisions."""
    journal: Journal = ctx.obj["journal"]

    if due:
        decisions = journal.list_due()
    elif pending:
        decisions = journal.list_pending()
    elif category:
        decisions = journal.list_by_category(category)
    else:
        decisions = journal.list_all()

    # Sort by timestamp, newest first
    decisions = sorted(decisions, key=lambda d: d.timestamp, reverse=True)[:limit]

    if not decisions:
        console.print("[dim]No decisions found.[/dim]")
        return

    table = Table(title="Decisions")
    table.add_column("ID", style="cyan")
    table.add_column("Date")
    table.add_column("Summary")
    table.add_column("Conf", justify="right")
    table.add_column("Status")
    table.add_column("Category", style="dim")

    for d in decisions:
        if d.outcome == Outcome.SUCCESS:
            status = "[green]✅ Success[/green]"
        elif d.outcome == Outcome.FAILURE:
            status = "[red]❌ Failure[/red]"
        elif d.outcome == Outcome.PARTIAL:
            status = "[yellow]⚡ Partial[/yellow]"
        elif d.outcome == Outcome.INCONCLUSIVE:
            status = "[dim]❓ Inconclusive[/dim]"
        elif d.is_due:
            status = "[yellow]⏰ Due![/yellow]"
        else:
            status = "[dim]⏳ Pending[/dim]"

        table.add_row(
            d.id,
            d.timestamp.strftime("%Y-%m-%d"),
            d.summary[:40] + ("..." if len(d.summary) > 40 else ""),
            f"{d.confidence:.0%}",
            status,
            d.category,
        )

    console.print(table)


@main.command()
@click.argument("decision_id")
@click.option("--outcome", "-o", type=click.Choice(["success", "failure", "partial", "inconclusive"]), required=True)
@click.option("--result", "-r", help="What actually happened")
@click.option("--lessons", "-l", help="What was learned")
@click.pass_context
def review(
    ctx: click.Context,
    decision_id: str,
    outcome: str,
    result: Optional[str],
    lessons: Optional[str],
) -> None:
    """Review a decision and record the outcome."""
    journal: Journal = ctx.obj["journal"]

    decision = journal.review(
        decision_id=decision_id,
        outcome=Outcome(outcome),
        actual_result=result,
        lessons=lessons,
    )

    if not decision:
        console.print(f"[red]Error:[/red] Decision '{decision_id}' not found.")
        raise SystemExit(1)

    console.print(f"[green]✓[/green] Decision reviewed: [bold]{decision.id}[/bold]")
    console.print(f"  Outcome: {outcome}")
    if decision.lessons:
        console.print(f"  Lessons: {decision.lessons}")


@main.command()
@click.argument("decision_id")
@click.pass_context
def show(ctx: click.Context, decision_id: str) -> None:
    """Show details of a specific decision."""
    journal: Journal = ctx.obj["journal"]

    decision = journal.get(decision_id)
    if not decision:
        console.print(f"[red]Error:[/red] Decision '{decision_id}' not found.")
        raise SystemExit(1)

    console.print(decision.to_markdown())


@main.command()
@click.pass_context
def stats(ctx: click.Context) -> None:
    """Show decision statistics."""
    journal: Journal = ctx.obj["journal"]

    s = journal.stats()
    console.print(str(s))


@main.command()
@click.option("--format", "-f", "fmt", type=click.Choice(["markdown", "json"]), default="markdown")
@click.pass_context
def export(ctx: click.Context, fmt: str) -> None:
    """Export all decisions."""
    journal: Journal = ctx.obj["journal"]

    if fmt == "markdown":
        output = journal.export_markdown()
    else:
        output = journal.export_json()

    click.echo(output)


@main.command()
@click.option(
    "--type",
    "-t",
    "plot_type",
    type=click.Choice(["calibration", "brier", "confidence", "reasons", "dashboard"]),
    default="dashboard",
    help="Type of plot to generate",
)
@click.option("--output", "-o", "output_path", help="Output file path (PNG)")
@click.option("--show", "-s", is_flag=True, help="Display plot interactively")
@click.option("--window", "-w", type=int, default=5, help="Rolling window size for Brier plot")
@click.pass_context
def plot(
    ctx: click.Context,
    plot_type: str,
    output_path: str | None,
    show: bool,
    window: int,
) -> None:
    """Generate calibration visualizations.

    Requires matplotlib: pip install agent-decisions[plots]

    Plot types:
      calibration - Reliability diagram (predicted vs actual)
      brier       - Brier score trend over time
      confidence  - Confidence distribution by outcome
      reasons     - Reason type effectiveness
      dashboard   - All plots in a 2x2 grid
    """
    if not PLOTS_AVAILABLE:
        console.print(
            "[red]Error:[/red] matplotlib not installed. "
            "Install with: pip install agent-decisions[plots]"
        )
        raise SystemExit(1)

    journal: Journal = ctx.obj["journal"]
    decisions = journal.list_all()

    if not decisions:
        console.print("[dim]No decisions found.[/dim]")
        return

    # Default output path if not specified and not showing
    if not output_path and not show:
        output_path = f"calibration_{plot_type}.png"

    try:
        if plot_type == "calibration":
            result = plots.plot_calibration(decisions, output_path, show=show)
        elif plot_type == "brier":
            result = plots.plot_brier_over_time(
                decisions, window_size=window, output_path=output_path, show=show
            )
        elif plot_type == "confidence":
            result = plots.plot_confidence_distribution(decisions, output_path, show=show)
        elif plot_type == "reasons":
            result = plots.plot_reason_effectiveness(decisions, output_path, show=show)
        else:  # dashboard
            result = plots.plot_dashboard(decisions, output_path, show=show)

        if result is None and output_path:
            console.print(f"[green]✓[/green] Plot saved to: [bold]{output_path}[/bold]")
        elif result is None:
            console.print("[dim]Not enough data for this plot.[/dim]")

    except Exception as e:
        console.print(f"[red]Error generating plot:[/red] {e}")
        raise SystemExit(1)


@main.command()
@click.option("--host", "-h", default="127.0.0.1", help="Host to bind to")
@click.option("--port", "-p", type=int, default=5000, help="Port to bind to")
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.pass_context
def serve(ctx: click.Context, host: str, port: int, debug: bool) -> None:
    """Start the web dashboard server.

    Requires Flask: pip install agent-decisions[web]

    Opens a web interface for browsing decisions, viewing stats,
    and generating calibration plots.
    """
    try:
        from .web.app import run_server
    except ImportError:
        console.print(
            "[red]Error:[/red] Flask not installed. "
            "Install with: pip install agent-decisions[web]"
        )
        raise SystemExit(1)

    journal_path = ctx.obj["journal"].directory
    console.print("[green]Starting web dashboard...[/green]")
    console.print(f"  URL: http://{host}:{port}")
    console.print(f"  Journal: {journal_path}")
    console.print("  Press Ctrl+C to stop")
    console.print()

    run_server(journal_path=journal_path, host=host, port=port, debug=debug)


@main.command()
@click.option("--fix", is_flag=True, help="Show suggestions for fixing low diversity")
@click.pass_context
def validate(ctx: click.Context, fix: bool) -> None:
    """Validate decisions for reason diversity.

    Checks all pending decisions for low reason diversity (< 50%).
    Decisions with correlated reasons (all same type) are fragile
    even when they feel well-supported.

    Inspired by noxious6's insight on Moltbook.
    """
    journal: Journal = ctx.obj["journal"]
    decisions = journal.list_pending()

    if not decisions:
        console.print("[dim]No pending decisions found.[/dim]")
        return

    low_diversity = []
    for d in decisions:
        if len(d.reasons) >= 2 and not d.has_diverse_reasons:
            low_diversity.append(d)

    if not low_diversity:
        console.print(
            f"[green]✓[/green] All {len(decisions)} pending decisions "
            "have diverse reasoning."
        )
        return

    console.print(
        f"[yellow]⚠️  {len(low_diversity)} decision(s) with "
        "low reason diversity:[/yellow]\n"
    )

    for d in low_diversity:
        console.print(f"[bold]{d.id}[/bold]: {d.summary[:50]}")
        console.print(f"  Confidence: {d.confidence:.0%}")
        console.print(f"  Diversity: {d.reason_diversity_score:.0%}")
        console.print(f"  Reasons ({len(d.reasons)}):")
        for r in d.reasons:
            text = r.text[:40] + ("..." if len(r.text) > 40 else "")
            console.print(f"    - [{r.reason_type.value}] {text}")

        warning = d.get_reason_diversity_warning()
        if warning:
            console.print(f"  [yellow]{warning}[/yellow]")

        if fix:
            # Suggest reason types not yet used
            used_types = set(r.reason_type for r in d.reasons)
            unused_types = set(ReasonType) - used_types
            suggestions = list(unused_types)[:3]
            type_list = ", ".join(t.value for t in suggestions)
            console.print(
                f"  [cyan]Suggestions:[/cyan] Add a reason of type: {type_list}"
            )

        console.print()

    console.print("[dim]Tip: Diverse reasoning types = more robust decisions[/dim]")


if __name__ == "__main__":
    main()
