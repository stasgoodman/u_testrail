import json
from pathlib import Path
from typing import Optional
import typer
from github import Github
from git import Repo
from rich.console import Console

app = typer.Typer()
console = Console()

# -------------------- GitHub Helpers -------------------- #
def get_github_repo(full_name: str, token: str):
    return Github(token).get_repo(full_name)


def find_or_create_pr(repo, branch: str, title: str, body: str):
    pulls = list(repo.get_pulls(state="open", head=f"{repo.owner.login}:{branch}"))
    if pulls:
        pr = pulls[0]
        pr.edit(title=title, body=body)
        console.print(f"[blue]ℹ️ Updated existing PR:[/blue] {pr.html_url}")
    else:
        pr = repo.create_pull(title=title, body=body, head=branch, base=repo.default_branch)
        console.print(f"[green]✅ Created PR:[/green] {pr.html_url}")


# -------------------- Git Helpers -------------------- #
def clone_repo(repo, token: str) -> Path:
    url = repo.clone_url.replace("https://", f"https://{token}@")
    path = Path("repos") / repo.full_name.replace("/", "--")
    if path.exists():
        return path
    return Repo.clone_from(url, path).working_dir


# -------------------- Main Command -------------------- #
@app.command()
def apply_changes_from_json(
    json_path: Path = typer.Argument(..., help="Path to JSON file with repo edits"),
    token: Optional[str] = typer.Option(None, envvar="GITHUB_TOKEN", help="GitHub token")
):
    """Apply multiple file or line edits across repos from a JSON spec."""
    if not token:
        raise typer.BadParameter("GitHub token required via --token or env GITHUB_TOKEN")

    updates = json.loads(json_path.read_text())
    for update in updates:
        repo_name = update["repo"]
        branch = update.get("branch", "auto-update")
        title = update.get("title", f"Update via CLI")
        body = update.get("body", "")
        edits = update["edits"]

        console.print(f"\n[bold cyan]🔁 Processing {repo_name}[/bold cyan]")
        try:
            gh_repo = get_github_repo(repo_name, token)
            repo_path = Path(clone_repo(gh_repo, token))
            repo = Repo(repo_path)

            try:
                repo.git.checkout("-b", branch)
            except:
                repo.git.checkout(branch)

            for edit in edits:
                file_target = repo_path / edit["file_path"]
                lines = file_target.read_text().splitlines() if file_target.exists() else []

                if "reference_path" in edit:
                    ref_text = Path(edit["reference_path"]).read_text()
                    file_target.write_text(ref_text)
                    console.print(f"[green]✅ Replaced:[/green] {edit['file_path']}")
                elif "line_number" in edit and "code_block" in edit:
                    idx = edit["line_number"] - 1
                    block = edit["code_block"].splitlines()
                    while len(lines) <= idx:
                        lines.append("")
                    lines[idx:idx+len(block)] = block
                    file_target.write_text("\n".join(lines) + "\n")
                    console.print(f"[green]✏️ Edited:[/green] {edit['file_path']} at line {edit['line_number']}")
                else:
                    console.print(f"[yellow]⚠️ Skipping invalid edit:[/yellow] {edit}")

            repo.git.add(all=True)
            repo.index.commit(title)
            repo.git.push("--set-upstream", "origin", branch)
            find_or_create_pr(gh_repo, branch, title, body)

        except Exception as e:
            console.print(f"[red]❌ Failed on {repo_name}:[/red] {e}")


if __name__ == "__main__":
    app()
    
    [
  {
    "repo": "stasgoodman/u_testrail",
    "branch": "auto-fix",
    "title": "Fix API client logic",
    "body": "Updated logic for error handling and authentication.",
    "edits": [
      {
        "file_path": "src/client.py",
        "line_number": 42,
        "code_block": "if not token:\n    raise ValueError(\"Missing token\")"
      },
      {
        "file_path": "README.md",
        "reference_path": "new_readme.md"
      }
    ]
  }
]

python app.py apply-changes-from-json changes.json

    
    
    