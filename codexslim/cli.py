"""CodexSlim CLI entry point."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from codexslim.core.engine import Engine


@click.command()
@click.argument("target", type=click.Path(exists=True, path_type=Path))
@click.option("--format", "fmt", default="skeleton", show_default=True,
              help="Output format: skeleton | manifest")
@click.option("--out", "out_path", default=None, type=click.Path(path_type=Path),
              help="Output path.")
@click.option("--dep-depth", default=1, show_default=True)
@click.option("--grace-period", default=24, show_default=True)
@click.option("--tokenizer", default="openai", show_default=True,
              type=click.Choice(["openai", "anthropic", "both"], case_sensitive=False))
@click.option("--no-cache", is_flag=True, default=False)
@click.option("--verbose", is_flag=True, default=False)
def main(target, fmt, out_path, dep_depth, grace_period, tokenizer, no_cache, verbose):
    """Slim a codebase for AI agent consumption."""
    workspace_root = target if target.is_dir() else target.parent
    engine = Engine(
        workspace_root=workspace_root,
        grace_hours=grace_period,
        tokenizer_backend=tokenizer,
        use_cache=not no_cache,
    )
    click.echo(f"CodexSlim  →  {target}")
    result = engine.run(target)

    if not result.files:
        click.echo("No supported source files found.", err=True)
        sys.exit(1)

    if fmt == "skeleton":
        _write_skeleton(result, out_path, verbose)
    elif fmt == "manifest":
        _write_manifest(result, out_path, verbose)
    else:
        click.echo(f"Format '{fmt}' not yet implemented.", err=True)
        sys.exit(1)

    click.echo(
        f"\n{len(result.files)} files  ·  {result.cache_hits} cache hits  ·  "
        f"{result.overall_savings_pct}% token savings"
    )


def _write_skeleton(result, out_path, verbose):
    if out_path is None:
        out_path = result.workspace_root / "slim-output"
    out_path.mkdir(parents=True, exist_ok=True)
    for slim_file in result.files:
        rel = slim_file.source_path.relative_to(result.workspace_root)
        dest = out_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(slim_file.slim_source, encoding="utf-8")
        if verbose:
            rep = slim_file.token_reports[0] if slim_file.token_reports else None
            hit = " (cached)" if slim_file.cache_hit else ""
            savings = f"{rep.savings_pct}% saved" if rep else ""
            click.echo(f"  {rel}  {savings}{hit}")
    click.echo(f"Skeleton written to {out_path}")


def _write_manifest(result, out_path, verbose):
    if out_path is None:
        out_path = result.workspace_root / "SLIM.md"
    lines = [
        "# SLIM.md — CodexSlim manifest", "",
        f"> {len(result.files)} files · {result.overall_savings_pct}% token savings", "",
    ]
    for slim_file in result.files:
        rel = slim_file.source_path.relative_to(result.workspace_root)
        lines += [f"## `{rel}`", "", f"```{slim_file.source_path.suffix.lstrip('.')}",
                  slim_file.slim_source.rstrip(), "```", ""]
    out_path.write_text("\n".join(lines), encoding="utf-8")
    click.echo(f"Manifest written to {out_path}")


if __name__ == "__main__":
    main()
