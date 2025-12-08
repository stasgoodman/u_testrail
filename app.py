import typer
from pathlib import Path
from typing import List, Optional
from github import Github
from git import Repo, GitCommandError
from rich.console import Console
from difflib import unified_diff
import shutil
import tempfile
import os

app = typer.Typer()
console = Console()


# ────────────────────────────────
# HELPERS
# ────────────────────────────────

def get_github_repos(token: str, repos: List[str]):
    gh = Github(token)
    return [gh.get_repo(r) for r in repos]

def clone_repo(repo, token: str) -> Path:
    tmp_dir = Path(tempfile.mkdtemp())
    repo_url = repo.clone_url.replace("https://", f"https://{token}@")
    try:
        Repo.clone_from(repo_url, tmp_dir)
    except GitCommandError as e:
        raise RuntimeError(f"Clone failed: {e}")
    return tmp_dir

def read_file_lines(file: Path) -> List[str]:
    return file.read_text().splitlines() if file.exists() else []


# ────────────────────────────────
# COMMAND: edit-file
# ────────────────────────────────

@app.command()
def edit_file(
    repos: List[str] = typer.Argument(...),
    file_path: str = typer.Option(...),
    insert_line: Optional[int] = typer.Option(None),
    edit_line: Optional[int] = typer.Option(None),
    text: Optional[str] = typer.Option(None),
    reference_path: Optional[str] = typer.Option(None),
    branch: str = "auto-edit",
    commit_msg: str = "chore: edit file",
    pr_title: str = "Automated file edit",
    pr_body: str = "This PR updates the target file as requested.",
    token: Optional[str] = typer.Option(None, envvar="GITHUB_TOKEN")
):
    if not token:
        raise typer.BadParameter("GitHub token required via --token or env GITHUB_TOKEN")

    if not text and not reference_path:
        raise typer.BadParameter("Either --text or --reference-path must be provided")

    # Load reference block
    if reference_path:
        text = Path(reference_path).read_text()

    for repo in get_github_repos(token, repos):
        console.print(f"\n[yellow]✏️ Editing:[/yellow] {repo.full_name}")
        try:
            path = clone_repo(repo, token)
            git = Repo(path)
            git.remotes.origin.pull(rebase=True)
            git.git.checkout("-b", branch)

            file_target = path / file_path
            lines = read_file_lines(file_target)

            if insert_line:
                idx = insert_line - 1
                while len(lines) < idx:
                    lines.append("")
                insert_lines = text.splitlines()
                lines[idx:idx] = insert_lines
            elif edit_line:
                if edit_line < 1:
                    console.print(f"[red]❌ Invalid edit line number:[/red] {edit_line}")
                    continue
                idx = edit_line - 1
                while len(lines) <= idx:
                    lines.append("")
                lines[idx] = text
            else:
                console.print("[red]❌ You must specify either --insert-line or --edit-line[/red]")
                continue

            file_target.write_text("\n".join(lines) + "\n")
            git.git.add(all=True)
            git.index.commit(commit_msg)
            git.git.push("--set-upstream", "origin", branch)

            pulls = list(repo.get_pulls(state="open", head=f"{repo.owner.login}:{branch}"))
            if pulls:
                pulls[0].edit(title=pr_title, body=pr_body)
                console.print(f"[green]✅ PR updated for:[/green] {repo.full_name}")
            else:
                repo.create_pull(title=pr_title, body=pr_body, head=branch, base=repo.default_branch)
                console.print(f"[green]✅ PR created for:[/green] {repo.full_name}")

        except Exception as e:
            console.print(f"[red]❌ Failed editing {repo.full_name}:[/red] {e}")


# ────────────────────────────────
# COMMAND: clone-repos
# ────────────────────────────────

@app.command()
def clone_repos(
    repos: List[str] = typer.Argument(...),
    token: Optional[str] = typer.Option(None, envvar="GITHUB_TOKEN")
):
    if not token:
        raise typer.BadParameter("GitHub token required")
    for repo in get_github_repos(token, repos):
        console.print(f"[blue]⏬ Cloning:[/blue] {repo.full_name}")
        try:
            path = clone_repo(repo, token)
            console.print(f"[green]✅ Cloned to:[/green] {path}")
        except Exception as e:
            console.print(f"[red]❌ Failed cloning {repo.full_name}:[/red] {e}")


# ────────────────────────────────
# COMMAND: delete-branch
# ────────────────────────────────

@app.command()
def delete_branch(
    repos: List[str] = typer.Argument(...),
    branch: str = typer.Option(...),
    token: Optional[str] = typer.Option(None, envvar="GITHUB_TOKEN")
):
    if not token:
        raise typer.BadParameter("GitHub token required")
    for repo in get_github_repos(token, repos):
        try:
            ref = repo.get_git_ref(f"heads/{branch}")
            ref.delete()
            console.print(f"[green]🗑 Deleted branch:[/green] {repo.full_name}@{branch}")
        except Exception as e:
            console.print(f"[red]❌ Failed to delete branch for {repo.full_name}:[/red] {e}")


# ────────────────────────────────
# COMMAND: check-function
# ────────────────────────────────

@app.command()
def check_function(
    repos: List[str] = typer.Argument(...),
    file_path: str = typer.Option(...),
    reference_path: str = typer.Option(...),
    token: Optional[str] = typer.Option(None, envvar="GITHUB_TOKEN")
):
    reference_code = Path(reference_path).read_text().strip().splitlines()
    if not token:
        raise typer.BadParameter("GitHub token required")

    for repo in get_github_repos(token, repos):
        try:
            path = clone_repo(repo, token)
            file = path / file_path
            if not file.exists():
                console.print(f"[red]❌ File missing in:[/red] {repo.full_name}")
                continue

            lines = read_file_lines(file)
            if reference_code != lines:
                diff = unified_diff(reference_code, lines, fromfile="reference", tofile=repo.full_name)
                console.print(f"[yellow]⚠️ Difference found in {repo.full_name}:[/yellow]")
                console.print("\n".join(diff))
            else:
                console.print(f"[green]✅ Function matches in:[/green] {repo.full_name}")

        except Exception as e:
            console.print(f"[red]❌ Error checking {repo.full_name}:[/red] {e}")


# ────────────────────────────────
# CLI USAGE EXAMPLES
# ────────────────────────────────
"""
USAGE:

# Insert a snippet at line 10
python main.py edit-file repo/name --file-path src/main.py --insert-line 10 --reference-path snippets/new_block.py

# Replace line 22
python main.py edit-file repo/name --file-path src/main.py --edit-line 22 --text "print('update')"

# Clone many repos
python main.py clone-repos repo1 repo2 repo3

# Delete branch across repos
python main.py delete-branch repo1 repo2 --branch feature123

# Check a function/code block
python main.py check-function repo1 repo2 --file-path src/main.py --reference-path ref/function.py
"""

if __name__ == "__main__":
    app()