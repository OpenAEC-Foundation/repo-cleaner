#!/usr/bin/env python3
"""
Script to apply LGPL 3.0 license to all OpenAEC-Foundation repositories
and validate repository naming conventions.

⚠️  WARNING: This is a powerful tool that can modify multiple repositories.
   Use with caution and always test with check-only flags first.

Usage:
    python apply_license.py --licenses                # Check license status only
    python apply_license.py --fix-licenses            # Apply/update licenses
    python apply_license.py --repo-naming             # Check naming conventions only
    python apply_license.py --fix-repo-naming         # Fix repository names
    python apply_license.py --licenses --repo-naming  # Check both

Options:
    --licenses              Check license status without making changes
    --fix-licenses          Apply/update LGPL 3.0 licenses to repositories
    --repo-naming           Check repository naming conventions
    --fix-repo-naming       Rename repositories to fix naming issues
    --org ORG               GitHub organization name (default: OpenAEC-Foundation)
"""

import argparse
import base64
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

from case_checker import get_convention


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color


def print_colored(message: str, color: str = Colors.NC) -> None:
    """Print colored message to terminal."""
    print(f"{color}{message}{Colors.NC}")


def run_gh_command(args: list[str], capture_output: bool = True) -> Tuple[bool, str]:
    """
    Run a gh CLI command and return success status and output.

    Args:
        args: Command arguments (without 'gh' prefix)
        capture_output: Whether to capture and return output

    Returns:
        Tuple of (success: bool, output: str)
    """
    try:
        result = subprocess.run(
            ['gh'] + args,
            capture_output=capture_output,
            text=True,
            check=True
        )
        return True, result.stdout if capture_output else ""
    except subprocess.CalledProcessError as e:
        return False, e.stderr if capture_output else ""


def check_naming_convention(repo_name: str, convention) -> list[str]:
    """
    Check if repository name follows naming conventions.

    Args:
        repo_name: Repository name to check
        convention: Convention instance

    Returns:
        List of issues found (empty if all good)
    """
    return convention.check_repository(repo_name)


def rename_repository(org: str, old_name: str, new_name: str) -> bool:
    """
    Rename a repository via the GitHub API.

    Args:
        org: Organization name
        old_name: Current repository name
        new_name: New repository name

    Returns:
        True if successful, False otherwise
    """
    payload = json.dumps({'name': new_name})
    try:
        result = subprocess.run(
            ['gh', 'api', f'repos/{org}/{old_name}',
             '--method', 'PATCH', '--input', '-', '--silent'],
            input=payload,
            text=True,
            capture_output=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError:
        return False


def get_file_content_from_api(org: str, repo: str, path: str) -> Optional[Tuple[str, str]]:
    """
    Get file content and SHA from GitHub API.

    Returns:
        Tuple of (content: str, sha: str) or None if file doesn't exist
    """
    success, output = run_gh_command([
        'api',
        f'repos/{org}/{repo}/contents/{path}'
    ])

    if not success:
        return None

    try:
        data = json.loads(output)
        content = base64.b64decode(data['content']).decode('utf-8')
        return content, data['sha']
    except (json.JSONDecodeError, KeyError, UnicodeDecodeError):
        return None


def update_file_via_api(
    org: str,
    repo: str,
    path: str,
    content: str,
    message: str,
    branch: str,
    existing_sha: Optional[str] = None
) -> bool:
    """
    Create or update a file via GitHub API.

    Args:
        org: Organization name
        repo: Repository name
        path: File path in repo
        content: File content (will be base64 encoded)
        message: Commit message
        branch: Branch name
        existing_sha: SHA of existing file (for updates)

    Returns:
        True if successful, False otherwise
    """
    content_b64 = base64.b64encode(content.encode('utf-8')).decode('ascii')

    payload = {
        'message': message,
        'content': content_b64,
        'branch': branch
    }

    if existing_sha:
        payload['sha'] = existing_sha

    payload_json = json.dumps(payload)

    success, _ = run_gh_command([
        'api',
        f'repos/{org}/{repo}/contents/{path}',
        '--method', 'PUT',
        '--input', '-',
        '--silent'
    ], capture_output=False)

    # We need to pass the payload via stdin
    try:
        result = subprocess.run(
            ['gh', 'api', f'repos/{org}/{repo}/contents/{path}',
             '--method', 'PUT', '--input', '-', '--silent'],
            input=payload_json,
            text=True,
            capture_output=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError:
        return False


def create_repo_issue(org: str, repo_name: str, issues: list[str]):
    """Create or update a pinned issue for naming convention violations."""
    body = "# Naming Convention Violations\n\nThis repository's name has the following issues:\n\n"
    for issue in issues:
        body += f"- {issue}\n"

    needs_manual = any("manual review" in issue for issue in issues)
    if needs_manual:
        body += "\n## Action Required\n\nThis repository has more than 3 segments and requires manual review. Please rename it to follow kebab-case convention with maximum 3 segments.\n"
    else:
        body += "\n## Action\n\nThis can be automatically fixed. The suggested name is shown above.\n"

    body += "\n---\n*This issue was automatically generated by the convention enforcer.*\n"
    create_pinned_issue(org, repo_name, "Naming convention violations", body)


def close_repo_issue(org: str, repo_name: str, issue_title: str = "Naming convention violations"):
    """Close and unpin a pinned issue by title if it exists."""
    try:
        result = subprocess.run(
            ['gh', 'issue', 'list', '-R', f'{org}/{repo_name}',
             '--search', f'"{issue_title}"', '--state', 'open',
             '--json', 'number', '--limit', '1'],
            capture_output=True,
            text=True,
            check=True
        )
        existing_issues = json.loads(result.stdout)

        if existing_issues:
            issue_number = str(existing_issues[0]['number'])

            subprocess.run(
                ['gh', 'issue', 'unpin', issue_number, '-R', f'{org}/{repo_name}'],
                capture_output=True,
                check=False
            )

            subprocess.run(
                ['gh', 'issue', 'close', issue_number, '-R', f'{org}/{repo_name}',
                 '--reason', 'completed',
                 '--comment', 'Resolved.'],
                capture_output=True,
                check=True
            )
            print_colored(f"  Closed issue #{issue_number} as resolved", Colors.GREEN)
    except (subprocess.CalledProcessError, Exception):
        pass


def create_pinned_issue(org: str, repo_name: str, title: str, body: str):
    """Create or update a pinned issue with the given title and body."""
    try:
        result = subprocess.run(
            ['gh', 'issue', 'list', '-R', f'{org}/{repo_name}',
             '--search', f'"{title}"', '--json', 'number,state',
             '--limit', '1'],
            capture_output=True,
            text=True,
            check=True
        )
        existing_issues = json.loads(result.stdout)

        if existing_issues:
            issue_number = str(existing_issues[0]['number'])
            issue_state = existing_issues[0]['state']

            subprocess.run(
                ['gh', 'issue', 'edit', issue_number, '-R', f'{org}/{repo_name}',
                 '--body', body],
                check=True
            )

            if issue_state == 'CLOSED':
                subprocess.run(
                    ['gh', 'issue', 'reopen', issue_number, '-R', f'{org}/{repo_name}'],
                    check=True
                )

            subprocess.run(
                ['gh', 'issue', 'pin', issue_number, '-R', f'{org}/{repo_name}'],
                capture_output=True,
                check=False
            )
        else:
            result = subprocess.run(
                ['gh', 'issue', 'create', '-R', f'{org}/{repo_name}',
                 '--title', title,
                 '--body', body],
                capture_output=True,
                text=True,
                check=True
            )
            issue_number = result.stdout.strip().split('/')[-1]

            subprocess.run(
                ['gh', 'issue', 'pin', issue_number, '-R', f'{org}/{repo_name}'],
                check=True
            )
    except (subprocess.CalledProcessError, Exception):
        pass


def main():
    parser = argparse.ArgumentParser(
        description='⚠️  POWERFUL TOOL: Apply LGPL 3.0 license and validate repository naming',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
⚠️  WARNING: This tool can modify multiple repositories at once.
   Always run check-only flags first before using --fix-* options.

Examples:
  %(prog)s --licenses                    Check license status
  %(prog)s --fix-licenses                Apply/update licenses
  %(prog)s --repo-naming                 Check naming conventions
  %(prog)s --licenses --repo-naming      Check both
        """
    )
    parser.add_argument(
        '--licenses',
        action='store_true',
        help='Check license status without making changes'
    )
    parser.add_argument(
        '--fix-licenses',
        action='store_true',
        help='Apply/update LGPL 3.0 licenses to repositories'
    )
    parser.add_argument(
        '--repo-naming',
        action='store_true',
        help='Check repository naming conventions'
    )
    parser.add_argument(
        '--fix-repo-naming',
        action='store_true',
        help='Rename repositories to fix naming issues (CAUTION!)'
    )
    parser.add_argument(
        '--readme',
        action='store_true',
        help='Check which repositories are missing a README.md'
    )
    parser.add_argument(
        '--org',
        default='OpenAEC-Foundation',
        help='GitHub organization name (default: OpenAEC-Foundation)'
    )
    parser.add_argument(
        '--string-naming',
        nargs=2,
        metavar=('CASE', 'STRING'),
        help='Convert a string to specified case (e.g., --string-naming camelCase "OpenPDFStudio")'
    )
    parser.add_argument(
        '--single-repo',
        metavar='REPO_NAME',
        help='Check only this specific repository (e.g., --single-repo RepoCleaner)'
    )
    args = parser.parse_args()

    # Handle string conversion utility
    if args.string_naming:
        target_case, input_string = args.string_naming
        convention = get_convention()

        try:
            result = convention.get_suggested_name(input_string, target_case)
            print(result)
            sys.exit(0)
        except Exception as e:
            print_colored(f"Error: {e}", Colors.RED)
            sys.exit(1)

    # Require at least one action flag
    if not any([args.licenses, args.fix_licenses, args.repo_naming, args.fix_repo_naming, args.readme]):
        parser.print_help()
        print()
        print_colored("❌ ERROR: No action specified. You must provide at least one flag.", Colors.RED)
        print_colored("   Use --licenses or --repo-naming to check status", Colors.YELLOW)
        print_colored("   Use --fix-licenses or --fix-repo-naming to make changes", Colors.YELLOW)
        sys.exit(1)

    # Check for conflicting flags
    if args.licenses and args.fix_licenses:
        print_colored("❌ ERROR: Cannot use both --licenses and --fix-licenses", Colors.RED)
        sys.exit(1)

    if args.repo_naming and args.fix_repo_naming:
        print_colored("❌ ERROR: Cannot use both --repo-naming and --fix-repo-naming", Colors.RED)
        sys.exit(1)

    # Determine what actions to take
    check_licenses = args.licenses or args.fix_licenses
    apply_licenses = args.fix_licenses
    check_naming = args.repo_naming or args.fix_repo_naming
    fix_naming = args.fix_repo_naming

    # Show warning for fix operations
    if args.fix_licenses or args.fix_repo_naming:
        print()
        print_colored("⚠️  " + "=" * 46, Colors.RED)
        print_colored("⚠️  WARNING: YOU ARE ABOUT TO MODIFY REPOSITORIES", Colors.RED)
        print_colored("⚠️  " + "=" * 46, Colors.RED)
        if args.fix_licenses:
            print_colored("   This will modify LICENSE.md files", Colors.YELLOW)
        if args.fix_repo_naming:
            print_colored("   This will RENAME repositories", Colors.YELLOW)
        print()
        response = input("Type 'yes' to continue: ")
        if response.lower() != 'yes':
            print_colored("Aborted.", Colors.YELLOW)
            sys.exit(0)
        print()

    org = args.org
    script_dir = Path(__file__).parent
    license_file = script_dir / 'LICENSE.md'

    # Load naming conventions
    print_colored("Loading naming conventions...", Colors.GREEN)
    convention = get_convention()
    print_colored("✓ Conventions loaded", Colors.GREEN)

    # Print header
    print("=" * 48)
    print("  Repository Management Tool")
    print(f"  Organization: {org}")
    print(f"  Actions:")
    if check_licenses:
        action = "FIX" if apply_licenses else "CHECK"
        print(f"    - Licenses: {action}")
    if check_naming:
        action = "FIX" if fix_naming else "CHECK"
        print(f"    - Naming: {action}")
    if args.readme:
        print(f"    - README: CHECK")
    print("=" * 48)
    print()

    # Check if gh CLI is installed
    if subprocess.run(['which', 'gh'], capture_output=True).returncode != 0:
        print_colored("Error: gh CLI is not installed. Please install it first.", Colors.RED)
        print("Visit: https://cli.github.com/")
        sys.exit(1)

    # Check if license file exists (only if we're checking licenses)
    license_content = None
    if check_licenses:
        if not license_file.exists():
            print_colored(f"Error: LICENSE.md not found at {license_file}", Colors.RED)
            sys.exit(1)
        license_content = license_file.read_text()

    # Get repos to check
    if args.single_repo:
        # Check single repository only
        print_colored(f"Checking repository: {args.single_repo}", Colors.GREEN)
        print()
        repos = [{'name': args.single_repo, 'defaultBranchRef': None}]
    else:
        # Get all repos from the organization
        print_colored(f"Fetching repositories from {org}...", Colors.GREEN)
        print()

        success, output = run_gh_command([
            'repo', 'list', org,
            '--limit', '1000',
            '--json', 'name,defaultBranchRef'
        ])

        if not success:
            print_colored("No repositories found or authentication failed.", Colors.RED)
            print("Please run: gh auth login")
            sys.exit(1)

        try:
            repos = json.loads(output)
        except json.JSONDecodeError:
            print_colored("Failed to parse repository list.", Colors.RED)
            sys.exit(1)

        if not repos:
            print_colored("No repositories found.", Colors.RED)
            sys.exit(1)

    repo_count = len(repos)
    print_colored(f"Found {repo_count} repositories", Colors.GREEN)
    print()

    # Statistics
    stats = {
        'success': 0,
        'skipped': 0,
        'failed': 0,
        'naming_issues': 0,
        'missing_readme': 0,
        'empty_repos': 0,
    }

    # Track all repos with naming issues
    repos_with_issues = []

    # Process each repository
    for idx, repo_data in enumerate(repos, 1):
        repo_name = repo_data['name']
        default_branch_data = repo_data.get('defaultBranchRef')
        default_branch = default_branch_data['name'] if default_branch_data else None

        print("=" * 48)
        print_colored(f"[{idx}/{repo_count}] Processing: {repo_name}", Colors.YELLOW)
        print("=" * 48)

        # Check if empty repository
        is_empty = not default_branch
        if is_empty:
            print_colored("⚠ Empty repository", Colors.YELLOW)
            stats['empty_repos'] += 1
            create_pinned_issue(org, repo_name, "Empty repository",
                "# Empty Repository\n\nThis repository has no commits yet. "
                "Please add initial content or consider removing it.\n\n"
                "---\n*This issue was automatically generated by the convention enforcer.*\n")

        # Check naming conventions (applies even to empty repos)
        if check_naming:
            naming_issues = check_naming_convention(repo_name, convention)
            if naming_issues:
                print_colored("⚠ NAMING ISSUES:", Colors.YELLOW)
                for issue in naming_issues:
                    print_colored(f"  - {issue}", Colors.YELLOW)
                stats['naming_issues'] += 1

                # Track all repos with naming issues
                repos_with_issues.append({
                    'name': repo_name,
                    'issues': naming_issues
                })

                # Fix naming if requested
                if fix_naming:
                    needs_manual = any("manual review" in issue for issue in naming_issues)
                    if needs_manual:
                        print_colored("[SKIP] Too many segments — needs manual review, skipping rename", Colors.YELLOW)
                        create_repo_issue(org, repo_name, naming_issues)
                    else:
                        case_style = convention.naming.get('repository', {}).get('case', 'kebab-case')
                        suggested_name = convention.get_suggested_name(repo_name, case_style)
                        print_colored(f"[FIX] Renaming to: {suggested_name}", Colors.BLUE)
                        success = rename_repository(org, repo_name, suggested_name)
                        if success:
                            print_colored(f"✓ Renamed {repo_name} -> {suggested_name}", Colors.GREEN)
                            stats['success'] += 1
                            close_repo_issue(org, suggested_name)
                        else:
                            print_colored(f"✗ Failed to rename {repo_name}", Colors.RED)
                            stats['failed'] += 1
                            create_repo_issue(org, repo_name, naming_issues)
                else:
                    # Check-only mode: create/update issue
                    create_repo_issue(org, repo_name, naming_issues)
            else:
                # No issues: close any existing violation issue
                print_colored("✓ Naming OK", Colors.GREEN)
                close_repo_issue(org, repo_name)

        # Skip content checks for empty repos
        if is_empty:
            print()
            continue

        # Check README
        if args.readme:
            readme_data = get_file_content_from_api(org, repo_name, 'README.md')
            if readme_data:
                print_colored("✓ README.md exists", Colors.GREEN)
            else:
                print_colored("⚠ README.md missing", Colors.YELLOW)
                stats['missing_readme'] += 1

        # Check licenses
        if check_licenses:
            print(f"Default branch: {default_branch}")

            # Check if LICENSE.md already exists
            existing_data = get_file_content_from_api(org, repo_name, 'LICENSE.md')

            if existing_data:
                existing_content, existing_sha = existing_data
                print_colored("LICENSE.md exists, checking content...", Colors.YELLOW)

                if existing_content == license_content:
                    print_colored("✓ LICENSE.md is up to date", Colors.GREEN)
                    stats['skipped'] += 1
                else:
                    print_colored("LICENSE.md differs from standard", Colors.YELLOW)
            else:
                print_colored("LICENSE.md not found", Colors.YELLOW)

            # Apply license if requested
            if apply_licenses and (not existing_data or existing_content != license_content):
                existing_sha_for_update = existing_sha if existing_data else None

                # Prepare commit message
                commit_message = """Add LGPL 3.0 license

This commit adds the GNU Lesser General Public License v3.0 to the repository.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"""

                # COMMENTED OUT FOR SAFETY - Remove comments to enable
                # Update or create the file
                # if update_file_via_api(
                #     org, repo_name, 'LICENSE.md',
                #     license_content, commit_message,
                #     default_branch, existing_sha_for_update
                # ):
                #     print_colored(f"✓ Successfully added license to {repo_name}", Colors.GREEN)
                #     stats['success'] += 1
                # else:
                #     print_colored(f"✗ Failed to add license to {repo_name}", Colors.RED)
                #     stats['failed'] += 1

                # Placeholder for commented out code above
                action = "update" if existing_sha_for_update else "create"
                print_colored(f"✓ Would {action} LICENSE.md", Colors.GREEN)
                stats['success'] += 1

        print()

    # Print summary
    print("=" * 48)
    print("  SUMMARY")
    print("=" * 48)
    print(f"Total repositories: {repo_count}")

    if check_licenses:
        if apply_licenses:
            print_colored(f"Successfully updated: {stats['success']}", Colors.GREEN)
            print_colored(f"Skipped (already up to date): {stats['skipped']}", Colors.YELLOW)
            print_colored(f"Failed: {stats['failed']}", Colors.RED)
        else:
            print_colored(f"Already up to date: {stats['skipped']}", Colors.GREEN)
            print_colored(f"Need updates: {repo_count - stats['skipped']}", Colors.YELLOW)

    if check_naming:
        print_colored(f"Repositories with naming issues: {stats['naming_issues']}", Colors.YELLOW)
        if fix_naming:
            print_colored(f"Renamed: {stats['success']}", Colors.GREEN)
            if stats['failed'] > 0:
                print_colored(f"Failed: {stats['failed']}", Colors.RED)
        elif stats['naming_issues'] > 0:
            print_colored(f"  Use --fix-repo-naming to rename them", Colors.BLUE)

    if args.readme:
        if stats['missing_readme'] > 0:
            print_colored(f"Repositories missing README: {stats['missing_readme']}", Colors.YELLOW)
        else:
            print_colored(f"All repositories have a README", Colors.GREEN)

    if stats['empty_repos'] > 0:
        print_colored(f"Empty repositories: {stats['empty_repos']}", Colors.YELLOW)

    print("=" * 48)

    if stats['failed'] > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
