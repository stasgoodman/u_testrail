@app.command("count-usage-from-file")
def count_usage_from_file(
    config_path: Path = typer.Argument(..., help="Path to JSON config file"),
    token: Optional[str] = typer.Option(None, envvar="GITHUB_TOKEN", help="GitHub token")
):
    """
    Count function usage across multiple GitHub repos using AST.
    Functions are derived dynamically from the keys of `counts` in the JSON file.
    Updates the same JSON file with the new total counts.
    """

    if not token:
        raise typer.BadParameter("GitHub token required via --token or env GITHUB_TOKEN")

    if not config_path.exists():
        raise typer.BadParameter(f"Config file not found: {config_path}")

    # ----------------- Load config -----------------
    config = json.loads(config_path.read_text())

    repos = config["repos"]
    folder = Path(config["folder"]) if "folder" in config and config["folder"] else None

    # 🔥 Function names now come from the keys of "counts"
    functions = list(config["counts"].keys())

    # Initialize totals
    global_counts = {fn: 0 for fn in functions}

    # ----------------- AST helper -----------------
    import ast

    def count_function_calls_clean(code: str, target_names):
        """
        Count REAL Python function calls, ignoring:
        - comments
        - strings
        - docstrings
        - logger.* or logging.* calls
        """
        class Visitor(ast.NodeVisitor):
            def __init__(self):
                self.counts = {name: 0 for name in target_names}

            def visit_Call(self, node):
                fname = None

                # Direct call: set_d(...)
                if isinstance(node.func, ast.Name):
                    fname = node.func.id

                # Attribute call: obj.set_d(...)
                elif isinstance(node.func, ast.Attribute):
                    # Ignore logger or logging calls
                    if isinstance(node.func.value, ast.Name):
                        if node.func.value.id in ("logger", "logging"):
                            return
                    fname = node.func.attr

                if fname in self.counts:
                    self.counts[fname] += 1

                self.generic_visit(node)

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return {fn: 0 for fn in target_names}

        v = Visitor()
        v.visit(tree)
        return v.counts

    # ----------------- Scan Repos -----------------
    for repo in get_github_repos(token, repos):
        console.print(f"\n[cyan]🔍 Scanning repo:[/cyan] {repo.full_name}")

        repo_path = clone_repo(repo, token)
        if not repo_path:
            continue

        scan_path = repo_path / folder if folder else repo_path
        if not scan_path.exists():
            console.print(f"[yellow]⚠ Folder '{folder}' not found in {repo.full_name}[/yellow]")
            continue

        # scan .py files
        for py_file in scan_path.rglob("*.py"):
            try:
                code = py_file.read_text(encoding="utf-8", errors="ignore")
                file_counts = count_function_calls_clean(code, functions)

                for fn, ct in file_counts.items():
                    global_counts[fn] += ct

            except Exception as e:
                console.print(f"[red]⚠ Error in file {py_file}: {e}[/red]")

        console.print(f"[green]✔ Completed:[/green] {repo.full_name}")

    # ----------------- Save results -----------------
    config["counts"] = global_counts
    config_path.write_text(json.dumps(config, indent=2))

    console.print(f"\n[bold green]📁 Updated usage counts saved to {config_path}[/bold green]")
    for fn, ct in global_counts.items():
        console.print(f"   • {fn}: [bold]{ct}[/bold]")
        
{
  "repos": ["stasgoodman/repo1", "stasgoodman/repo2"],
  "folder": "src/",
  "counts": {
    "get_d": 0,
    "set_d": 0
  }
}
        