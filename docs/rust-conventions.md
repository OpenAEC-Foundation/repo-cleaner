# Rust conventions

The convention enforcer follows the Rust project's own naming and formatting rules. The rules are not derived from a third-party community guide.

| Rust item | Convention-enforcer category | Required case |
| --- | --- | --- |
| Crates, modules, and namespaces | `namespace` | `snake_case` |
| Types, traits, type aliases, and type parameters | `class` | `PascalCase` (`UpperCamelCase` in Rust terminology) |
| Functions, methods, and macros | `function` | `snake_case` |
| Local variables, parameters, and struct fields | `variable` | `snake_case` |
| Constants and static variables | `constant` | `SCREAMING_SNAKE_CASE` |
| Enums and enum variants | `enum` | `PascalCase` (`UpperCamelCase` in Rust terminology) |
| Rust source files and module directories | `file` / `directory` | `snake_case` |

Formatting is performed by `cargo fmt --all`. Symbol and path renames are prepared by rust-analyzer. The compiler's `nonstandard_style` lint family supplies naming diagnostics for bindings and type parameters that rust-analyzer does not expose as document symbols.

Primary sources:

- [Names in the official Rust Style Guide](https://doc.rust-lang.org/style-guide/advice.html#names)
- [Rust RFC 430: Finalizing naming conventions](https://rust-lang.github.io/rfcs/0430-finalizing-naming-conventions.html)
- [The rustc `nonstandard-style` lint group](https://doc.rust-lang.org/rustc/lints/groups.html#nonstandard-style)
