@app.command("clone-repos")
def clone_repos(
    repos: List[str] = typer.Argument(..., help="List of GitHub repositories to clone"),
    token: Optional[str] = typer.Option(None, envvar="GITHUB_TOKEN", help="GitHub token")
):
    """
    Clone one or more GitHub repositories locally into ./repos/<repo_name>.
    """
    if not token:
        raise typer.BadParameter("GitHub token required via --token or env GITHUB_TOKEN")

    for repo_full_name in repos:
        try:
            gh = Github(token)
            repo = gh.get_repo(repo_full_name)
        except Exception as e:
            console.print(f"[red]❌ Cannot access repo:[/red] {repo_full_name} → {e}")
            continue

        local_path = Path("repos") / repo.name
        if local_path.exists():
            console.print(f"[yellow]⚠️ Repo already exists, skipping:[/yellow] {repo_full_name}")
            continue

        clone_url = repo.clone_url.replace("https://", f"https://{token}@")
        console.print(f"[cyan]🔄 Cloning:[/cyan] {repo_full_name} → {local_path}")
        try:
            Repo.clone_from(clone_url, local_path)
            console.print(f"[green]✅ Cloned:[/green] {repo_full_name}")
        except Exception as e:
            console.print(f"[red]❌ Failed to clone {repo_full_name}:[/red] {e}")