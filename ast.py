@app.command("count-usage-from-file")
def count_usage_from_file(
    config_path: Path = typer.Argument(..., help="Path to JSON config file"),
    token: Optional[str] = typer.Option(None, envvar="GITHUB_TOKEN", help="GitHub token")
):
    """
    Count function usage across multiple GitHub repos as defined in a JSON file.
    Updates the same file with actual counts.
    """
    if not token:
        raise typer.BadParameter("GitHub token required via --token or env GITHUB_TOKEN")

    if not config_path.exists():
        raise typer.BadParameter(f"Config file not found: {config_path}")

    config = json.loads(config_path.read_text())
    functions = config["functions"]
    repos = config["repos"]
    folder = Path(config["folder"]) if "folder" in config and config["folder"] else None

    # AST scanner
    import ast
    def count_function_calls_clean(code: str, target_names):
        class Visitor(ast.NodeVisitor):
            def __init__(self):
                self.counts = {name: 0 for name in target_names}

            def visit_Call(self, node):
                fname = None
                if isinstance(node.func, ast.Name):
                    fname = node.func.id
                elif isinstance(node.func, ast.Attribute):
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
            return {name: 0 for name in target_names}

        v = Visitor()
        v.visit(tree)
        return v.counts

    global_counts = {fn: 0 for fn in functions}

    for repo in get_github_repos(token, repos):
        console.print(f"\n[cyan]🔍 Scanning:[/cyan] {repo.full_name}")
        repo_path = clone_repo(repo, token)
        if not repo_path:
            continue

        base_path = repo_path / folder if folder else repo_path
        if not base_path.exists():
            console.print(f"[yellow]⚠ Folder '{folder}' not found in {repo.full_name}[/yellow]")
            continue

        for py_file in base_path.rglob("*.py"):
            try:
                code = py_file.read_text(encoding="utf-8", errors="ignore")
                file_counts = count_function_calls_clean(code, functions)
                for fn, ct in file_counts.items():
                    global_counts[fn] += ct
            except Exception as e:
                console.print(f"[red]⚠ Error in {py_file}: {e}[/red]")

    config["counts"] = global_counts
    config_path.write_text(json.dumps(config, indent=2))

    console.print(f"\n[green]✔ Done. Updated counts saved in:[/green] {config_path}")
    for fn, ct in global_counts.items():
        console.print(f"   • {fn}: [bold]{ct}[/bold]")