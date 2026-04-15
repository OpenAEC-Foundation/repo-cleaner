#!/usr/bin/env python3
"""
Naming convention checker.
Fetches and applies OpenAEC Foundation naming conventions.
"""

import base64
import re
import subprocess
from pathlib import Path
from typing import List, Optional, Callable

try:
    import yaml
except ImportError:
    print("Error: pyyaml not installed. Run: pip install pyyaml")
    raise


# Case conversion functions
def extract_words(name: str) -> List[str]:
    """Extract words from any casing style and return them lowercase."""
    # Verify name contains at least one letter
    if not re.search(r'[a-zA-Z]', name):
        raise ValueError(f"Name must contain at least one letter: '{name}'")

    # Strip leading/trailing hyphens and underscores
    name = name.strip('-_')

    # Handle snake_case and kebab-case
    if '_' in name or '-' in name:
        return [w.lower() for w in re.split(r'[-_]', name)]

    # Handle PascalCase/camelCase - split on capitals
    words = re.findall(r'[A-Z]?[a-z0-9]+|[A-Z]+(?=[A-Z][a-z]|\b)', name)
    return [w.lower() for w in words] if words else [name.lower()]


def convert_case(name_or_words, target_case: str) -> str:
    """
    Convert to target case. Merges first letters if >3 segments.

    Args:
        name_or_words: String name or list of pre-extracted words
        target_case: 'kebab-case', 'snake_case', 'camelCase', or 'PascalCase'
    """
    # Extract words if string provided
    if isinstance(name_or_words, str):
        words = extract_words(name_or_words)
    else:
        words = name_or_words

    # Merge if > 3 segments
    if len(words) > 3:
        words = [''.join(w[0] for w in words)]

    # Apply target case
    if target_case == 'kebab-case':
        return '-'.join(words)
    elif target_case == 'snake_case':
        return '_'.join(words)
    elif target_case == 'camelCase':
        return words[0] + ''.join(w.capitalize() for w in words[1:])
    elif target_case == 'PascalCase':
        return ''.join(w.capitalize() for w in words)


# Supported case styles
CASE_STYLES = ['kebab-case', 'snake_case', 'camelCase', 'PascalCase']


# Case pattern registry
CASE_PATTERNS: dict[str, str] = {
    'kebab-case': r'^[a-z0-9]+(-[a-z0-9]+)*$',
    'snake_case': r'^[a-z][a-z0-9_]*$',
    'camelCase': r'^[a-z][a-zA-Z0-9]*$',
    'PascalCase': r'^[A-Z][a-zA-Z0-9]*$',
}


class Convention:
    """Stores and applies naming conventions."""

    CACHE_PATH = Path.home() / '.cache' / 'openaec-conventions.yaml'
    REPO = 'OpenAEC-Foundation/conventions'
    FILE_PATH = 'conventions.yaml'

    def __init__(self, conventions_dict: dict = None):
        """
        Initialize convention checker.

        Args:
            conventions_dict: Pre-loaded conventions, or None to fetch
        """
        if conventions_dict is None:
            conventions_dict = self._load()

        self.data = conventions_dict
        self.naming = conventions_dict.get('naming', {})
        self.cases = self.naming.get('case', {})

    def _fetch_from_github(self) -> str:
        """Fetch conventions.yaml content from GitHub."""
        try:
            result = subprocess.run(
                ['gh', 'api', f'repos/{self.REPO}/contents/{self.FILE_PATH}',
                 '--jq', '.content'],
                capture_output=True,
                text=True,
                check=True
            )
            return base64.b64decode(result.stdout).decode('utf-8')
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to fetch conventions from {self.REPO}/{self.FILE_PATH}\n"
                f"Error: {e}\n"
                f"Make sure gh CLI is authenticated: gh auth login"
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"Failed to decode conventions file from GitHub\n"
                f"Error: {e}"
            ) from e

    def _load(self) -> dict:
        """Load conventions from cache or GitHub."""
        # Try cache first
        if self.CACHE_PATH.exists():
            try:
                content = self.CACHE_PATH.read_text()
                return yaml.safe_load(content)
            except yaml.YAMLError as e:
                raise RuntimeError(
                    f"Cached conventions file is corrupted: {self.CACHE_PATH}\n"
                    f"Error: {e}\n"
                    f"Delete it and try again"
                ) from e
            except Exception:
                # Cache failed, try fetching
                pass

        # Fetch from GitHub
        content = self._fetch_from_github()

        # Save to cache
        self.CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.CACHE_PATH.write_text(content)

        try:
            return yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise RuntimeError(
                f"Conventions file from {self.REPO} is not valid YAML\n"
                f"Error: {e}\n"
                f"This is a bug in the conventions repository"
            ) from e

    def refresh(self):
        """Refresh conventions from GitHub."""
        content = self._fetch_from_github()
        self.CACHE_PATH.write_text(content)
        self.data = yaml.safe_load(content)
        self.naming = self.data.get('naming', {})
        self.cases = self.naming.get('case', {})

    def get_pattern(self, case_name: str) -> Optional[str]:
        """Get regex pattern for a case style."""
        # Try conventions file first, fall back to built-in patterns
        pattern = self.cases.get(case_name, {}).get('pattern')
        if pattern:
            return pattern
        return CASE_PATTERNS.get(case_name)

    def check(self, name: str, case_name: str) -> List[str]:
        """
        Check if name matches case style.

        Args:
            name: Name to check
            case_name: Case style (e.g., 'kebab-case')

        Returns:
            List of issues (empty if valid)
        """
        issues = []
        pattern = self.get_pattern(case_name)

        if not pattern:
            return [f"Unknown case style: {case_name}"]

        words = extract_words(name)

        if len(words) > 3:
            issues.append("Too many segments (>3) - needs manual review")
        elif not re.match(pattern, name):
            issues.append(f"Does not match {case_name}")
            suggested = convert_case(words, case_name)
            if suggested != name:
                issues.append(f"Suggested: '{suggested}'")

        return issues

    def check_repository(self, name: str) -> List[str]:
        """Check repository name."""
        case_style = self.naming.get('repository', {}).get('case')
        if not case_style:
            return ["No repository convention defined"]
        return self.check(name, case_style)

    def check_directory(self, name: str) -> List[str]:
        """Check directory name."""
        case_style = self.naming.get('directory', {}).get('case')
        if not case_style:
            return ["No directory convention defined"]
        return self.check(name, case_style)

    def check_language(self, name: str, language: str, element_type: str) -> List[str]:
        """
        Check language-specific name.

        Args:
            name: Name to check
            language: Language (e.g., 'cpp', 'javascript')
            element_type: Element type (e.g., 'function', 'class', 'file')

        Returns:
            List of issues
        """
        lang = self.naming.get('language', {}).get(language, {})
        if not lang:
            return [f"No conventions for language: {language}"]

        case_style = lang.get(element_type)
        if not case_style:
            return [f"No convention for {language} {element_type}"]

        return self.check(name, case_style)

    def get_suggested_name(self, name: str, case_name: str) -> str:
        """Get suggested name for a case style."""
        return convert_case(name, case_name)


# Global instance
_convention: Optional[Convention] = None

def get_convention() -> Convention:
    """Get global Convention instance."""
    global _convention
    if _convention is None:
        _convention = Convention()
    return _convention
