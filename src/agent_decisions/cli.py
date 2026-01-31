"""
Command-line interface for agent-decisions.
"""

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from .journal import Journal
from .models import MentalState, Outcome, ReasonType, Stakes

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
@click.option("--related", multiple=True, help="Related decision IDs (K-line hierarchy)")
@click.option("--mental-state", "-m", type=click.Choice(["deliberate", "reactive", "exploratory", "habitual", "pressured"]), help="Mental state when deciding")
@click.option("--teaching-notes", help="Notes for future self")
@click.option("--reason", "-R", multiple=True, help="Reason supporting decision: 'type:text' or 'type:text:strength' (e.g., 'pattern:Similar to X which worked:0.8')")
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
) -> None:
    """Log a new decision."""
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
        related_decisions=list(related),
        mental_state=MentalState(mental_state) if mental_state else None,
        teaching_notes=teaching_notes,
        reasons=parsed_reasons,
    )
    
    console.print(f"[green]✓[/green] Decision logged: [bold]{decision.id}[/bold]")
    console.print(f"  Summary: {decision.summary}")
    console.print(f"  Confidence: {decision.confidence:.0%}")
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


if __name__ == "__main__":
    main()
