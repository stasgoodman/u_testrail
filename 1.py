@app.command("count-usage")
def count_usage(
    repos: List[str] = typer.Option(..., help="List of GitHub repos to scan"),
    functions: List[str] = typer.Option(..., help="Function names to count"),
    subdir: Optional[str] = typer.Option(None, help="Optional subfolder to limit search"),
    token: Optional[str] = typer.Option(None, envvar="GITHUB_TOKEN")
):
    """
    Count how many times specific function names are used across files in GitHub repos.
    """
    if not token:
        raise typer.BadParameter("GitHub token required via --token or env GITHUB_TOKEN")

    for repo in get_github_repos(token, repos):
        console.print(f"\n[bold blue]🔍 Checking:[/bold blue] {repo.full_name}")
        try:
            path = clone_repo(repo, token)
            target_path = path / subdir if subdir else path
            if not target_path.exists():
                console.print(f"[red]❌ Subdirectory does not exist:[/red] {target_path}")
                continue

            counts = {fn: 0 for fn in functions}

            for file in target_path.rglob("*.py"):
                try:
                    content = file.read_text()
                    for fn in functions:
                        counts[fn] += content.count(f"{fn}(")
                except Exception as e:
                    console.print(f"[red]⚠️ Failed to read:[/red] {file} - {e}")

            for fn, count in counts.items():
                console.print(f"[green]{fn}[/green] used [yellow]{count}[/yellow] times in [cyan]{repo.full_name}[/cyan]")

        except Exception as e:
            console.print(f"[red]❌ Failed processing {repo.full_name}:[/red] {e}")