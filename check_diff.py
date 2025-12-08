from difflib import unified_diff

@app.command()
def check_code(
    repos: List[str] = typer.Argument(..., help="Repos to check"),
    file_path: str = typer.Option(..., help="Path to target file in repo"),
    search_line: str = typer.Option(..., help="Line to match or start from"),
    reference_path: Optional[str] = typer.Option(None, help="Path to local file with reference block"),
    is_function: bool = typer.Option(True, help="Extract full function block (True) or match single/multi-line block (False)"),
    token: Optional[str] = typer.Option(None, envvar="GITHUB_TOKEN")
):
    """Check if a code line or block exists in file(s) and matches reference."""
    if not reference_path:
        console.print("[red]❌ reference_path is required[/red]")
        raise typer.Exit()

    reference_code = Path(reference_path).read_text().strip().splitlines()

    for repo in get_github_repos(token, repos):
        console.print(f"\n[blue]🔍 Checking:[/blue] {repo.full_name}")
        try:
            path = clone_repo(repo, token)
            file_target = path / file_path
            if not file_target.exists():
                console.print(f"[red]❌ File not found:[/red] {file_path}")
                continue

            file_lines = file_target.read_text().splitlines()
            start_idx = next((i for i, line in enumerate(file_lines) if search_line in line), -1)

            if start_idx == -1:
                console.print(f"[yellow]⚠️ Line not found:[/yellow] {search_line}")
                continue

            if is_function:
                # Extract function block based on indentation
                ref_indent = len(file_lines[start_idx]) - len(file_lines[start_idx].lstrip())
                block = []
                for line in file_lines[start_idx:]:
                    if line.strip() == "":
                        block.append(line)
                        continue
                    indent = len(line) - len(line.lstrip())
                    if indent < ref_indent and block:
                        break
                    block.append(line)
            else:
                # Just take N lines (or until blank) from search_line
                block = []
                for line in file_lines[start_idx:]:
                    if line.strip() == "":
                        break
                    block.append(line)

            diff = list(unified_diff(reference_code, block, lineterm=""))
            if not diff:
                console.print("[green]✅ Code block matches.[/green]")
            else:
                console.print("[yellow]⚠️ Code block differs:[/yellow]")
                for line in diff:
                    if line.startswith('+'):
                        console.print(f"[green]{line}[/green]")
                    elif line.startswith('-'):
                        console.print(f"[red]{line}[/red]")
                    else:
                        console.print(line)

        except Exception as e:
            console.print(f"[red]❌ Error checking {repo.full_name}:[/red] {e}")
            
            
"""
python main.py check-code \
  stasgoodman/u_testrail \
  --file-path "tests/test_client.py" \
  --search-line "def normalize_text" \
  --reference-path "examples/snippets/normalize_text.py" \
  --is-function True
"""