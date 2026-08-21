# OpenAEC Foundation Convention Enforcer

The convention enforcer is written in DynLex. It checks organization repositories against `OpenAEC-Foundation/conventions` and uses language servers for reference-safe code renames.

## Checks

- Repository names, including the three-segment limit
- Directory and source-file names
- PHP, C++, and JavaScript symbols
- Source files over 1000 lines
- `README.md`
- The standard `LICENSE.md`
- Empty repositories

Hidden metadata, dependency-owned `node_modules`, `vendor`, and `third_party` trees, and generated `dist` trees are excluded from convention fixes and size findings. C++ symbol fixes require a root `compile_commands.json`; JavaScript symbol fixes require a root `jsconfig.json` or `tsconfig.json`. Without project-wide index input, symbol violations remain report-only.

Safe code fixes run in a temporary clone. The enforcer asks one language server per detected language to update references, applies live renames one at a time, formats C++ sources with `clang-format`, and refreshes the repository tree after structural changes. Directory renames are prepared by every active language server before mutation. Servers with `workspace/didRenameFiles` stay active after the notification; a server that only implements `workspace/willRenameFiles` is shut down and recreated after the rename. A path violation remains report-only when any required server cannot safely prepare it. The enforcer publishes code fixes to `repo-cleaner/convention-fixes` and creates, updates, or closes one scanner-owned pull request.

Repository naming and empty-repository findings use exact-title pinned issues. Four-or-more-segment repository names are left for manual review.

## Requirements

- DynLex `master` with stable structural variable-flow inference
- Git and an authenticated GitHub CLI
- OpenAEC clangd with transactional file and directory rename support (`clangd-file-rename-core` until merged)
- `clang-format`
- Phpactor
- `typescript-language-server` with TypeScript

The reusable GitHub Actions workflow checks out and builds the required DynLex and LLVM revisions itself. Stock clangd does not implement the file-operation protocol required for reference-safe directory renames.

The installed TypeScript language server advertises `willRenameFiles` but not `didRenameFiles`, so JavaScript paths are renamed from its prepared workspace edit and the server is recreated before later operations. Phpactor's file-operation implementation is not complete enough for safe path changes, so PHP path violations remain report-only. JavaScript symbol renames use the TypeScript language server when a root project configuration is present; PHP symbol renames continue to use Phpactor. The enforcer never falls back to a reference-unsafe filesystem rename.

## Build and test

```bash
./scripts/build.sh
./scripts/test.sh
```

Set `DYNLEX=/path/to/dynlex` when the compiler is not on `PATH`. Put the required OpenAEC clangd ahead of any stock clangd on `PATH` when running path-backend integration tests or applying C++ path fixes.

C++ symbol fixes require a readable `compile_commands.json` at the repository root, and JavaScript symbol fixes require a root `jsconfig.json` or `tsconfig.json`. Without project-wide index input, symbol violations remain report-only because the language server cannot prove that a workspace edit covers cross-file references.

## Usage

Check one repository without publishing code changes:

```bash
./build/repo-conventions-enforcer \
  --repo-naming \
  --code-conventions \
  --readme \
  --single-repo repo-cleaner
```

Apply safe code fixes and maintain the scanner pull request:

```bash
./build/repo-conventions-enforcer \
  --fix-code-conventions \
  --single-repo repo-cleaner
```

Other actions:

```text
--licenses                 Check LICENSE.md
--fix-licenses             Create or replace LICENSE.md
--repo-naming              Check repository names and maintain issue state
--fix-repo-naming          Rename repositories when the fix is unambiguous
--readme                   Check README.md
--string-naming CASE TEXT  Convert text to a configured case
--org ORGANIZATION         Select the organization
--single-repo NAME         Process only one repository
```

`--fix-licenses` writes directly to the default branch, and `--fix-repo-naming` renames repositories directly. Code fixes use the scanner branch and pull request instead.

Without `--single-repo`, the selected actions run across the organization. Convention data is cached for 24 hours in the platform user-cache directory and replaced atomically.

The process exits nonzero after completing its work when it found violations, published fixes, or encountered a failure. This lets CI publish a fix pull request while keeping the check visibly unresolved.

## GitHub Actions

Call `.github/workflows/check-conventions.yml` and provide a token with repository contents, issues, and pull-request access. The workflow checks repository naming and README state and publishes safe code-convention fixes. `dynlex_ref` defaults to DynLex `master`. `llvm_project_ref` defaults to the OpenAEC clangd feature branch named in Requirements until that support merges.

## License

LGPL 3.0
