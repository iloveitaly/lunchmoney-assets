Coding instructions for all programming languages:

- Never use emojis anywhere unless explicitly requested.
- If no language is specified, assume the latest version of python.
- If tokens or other secrets are needed, pull them from an environment variable
- Prefer early returns over nested if statements.
- Prefer `continue` within a loop vs nested if statements.
- Prefer smaller functions over larger functions. Break up logic into smaller chunks with well-named functions.
- Use named constants for magic numbers, service urls, etc. Do not duplicate magic strings or numbers in code.
- Prefer constants with separators: `10_000` is preferred to `10000` (or `10_00` over `1000` in the case of a integer representing cents).
- Prefix feature-flag style constants with `{DISABLED,ENABLED}_`
- When I ask you to write code, prioritize simplicity and legibility over covering all edge cases, handling all errors, etc.
- When a particular need can be met with a mature, reasonably adopted and maintained package, I would prefer to use that package rather than engineering my own solution.
- Never add error handling to catch an error without being asked to do so. Fail hard and early with assertions and allow exceptions to propagate.
- When naming variables or functions, use names that describe the effect. For example, instead of `function handleClaimFreeTicket` (a function which opens a dialog box) use `function openClaimFreeTicketDialog`.
- Do not install missing system packages! Instead, ask me to install them for you.
- If terminal commands are failing because of missing variables or commands which are unrelated to your current task, stop your work and let me know.
- Don't worry about fixing lint errors or running lint scripts unless I specifically ask you to.
- When implementing workarounds for tooling limitations (like using `Any` for unresolvable types) or handling non-obvious edge cases, always add a brief inline comment explaining the technical reasoning.
- Reserve exact-width `#`-box section separators for long files requiring organization, though they should not be necessary in the large majority of cases (separate files is generally better).
- Complex functions, classes, etc (i.e. more than 10 lines or so) should have a concise docstr or comment describing their purpose.

Use line breaks to organize code into logical groups. Instead of:

```python
if not client_secret_id:
    raise ClientError("Invalid client secret")
session_id = client_secret_id.split("_secret")[0]
```

Prefer:

```python
if not client_secret_id:
    raise ClientError("Invalid client secret")

session_id = client_secret_id.split("_secret")[0]
```

**DO NOT FORGET**: keep your responses short, dense, and without fluff. I am a senior, well-educated software engineer, and hate long explanations.

### Code Comments

Default to no comment. Names, structure, and the command itself should explain what the code does.

The reader is a world-class engineer who may not know this domain or every third-party system. Add a concise one-line comment only when they would otherwise miss *why*:

- a business rule the code can't express
- non-obvious behavior or a gotcha in an external API, library, or tool
- a workaround for a tooling limitation (e.g. `Any` for an unresolvable type)
- a non-obvious edge case being handled

If the comment restates the next line, its names, or the command's flags, delete it.

Bad, restates the command:

```just
# install shared agent skills into the global skills dir
pnpx skills add https://github.com/iloveitaly/ai-skills -g --all
```

Good, explains a tool limitation the code can't show:

```just
# docker can't copy files out of an image, only a container, so create a throwaway one
docker create --name tmp-js-container {{JAVASCRIPT_IMAGE_TAG}}
docker cp tmp-js-container:/app/build/production/client public
```

- Describe behavior as it exists today—don't frame comments around version history or "old vs new."
- Do not remove existing comments.
- Do not capitalize or add periods at the end of single-line comments.

### Git Usage

- Do not automatically commit changes unless I explicitly ask you to.
- Never generate merge commits.

### Important Workflow Rules

Pay careful attention to these instructions when running tests, generating database migrations, or otherwise figuring out how to operate this project:

- Run `just` to understand the more important workflow commands.
  - Run `just --list` to see all available pre-written workflow development commands.
- **IMPORTANT:** Never manually set environment variables that are required. You can set optional variables for debugging, but any missing required environment variables is an error that should be reported and you should stop your work immediately.
- Do not worry about cleaning up the environment. This is done automatically.
- Run python code with `uv run python`
- Use `pytest` to run tests. If tests fail because of a configuration, environment, or system error: let me know and stop working.
  - Initially run `pytest --ignore=tests/integration` then only run `pytest tests/integration`
  - When debugging integration tests look at `$PLAYWRIGHT_RESULT_DIRECTORY`. There's a directory for each test failure. In that directory you fill find a `failure.html` containing the rendered DOM of the page on failure and a screenshot of the contents. Use these to debug why it failed.
- Do not attempt to create or run database migrations. Pause your work and let me know you need a migration run.
  - If you receive errors about missing migrations, missing tables, database connectivity, etc, stop your work and let me know.

## Python

globs: **/*.py

When writing Python:

* Assume the latest python, version 3.13.
* Prefer Pathlib methods (including read and write methods, like `read_text`) over `os.path`, `open`, `write`, etc.
* docstrs and comments:
  * If a docstring needs formatting, use markdown. Use Google Style.
  * Prefer docstr to multi-line comments at the top of a function or file.
  * If a docstr does not span multiple lines, do not use triple-quoted strings.
  * If a comment or docstr is a single line, do not end it in a period.
  * Add a newline after all docstrs.
* Do not create `__init__` files unless specifically instructed
* Use Pydantic models over dataclass or a typed dict.
* Use SQLAlchemy for generating any SQL queries.
* Use `click` for command line argument parsing.
* Use `log.info("the message", the_variable=the_variable)` instead of `log.info("The message: %s", the_variable)` or `print` for logging. This object can be found at `from app import log`.
  * Log messages should be lowercase with no leading or trailing whitespace.
  * No variable interpolation in log messages.
  * Do not coerce database IDs, dates, or Path objects to `str`
* Do not fix import ordering or other linting issues.
* Never edit or create any files in `migrations/versions/`
* Place all comments on dedicated lines immediately above the code statements they describe. Avoid inline comments appended to the end of code lines.
* Do not `try/catch` raw `Exceptions` unless explicitly told to. Prefer to let exceptions raise and cause an explicit error.
* Always make an explicit copy before mutating a dictionary that you did not create in the current narrow scope.
* Never use `from __future__`
* Always use `re.compile(pattern, re.VERBOSE)` and inline `#` comments to document the logic of each capture group or condition in any complex regular expression.
* **IMPORTANT** never edit app/generated/ files. These are autogenerated.

### Package Management

- Use `uv add` to add python packages. No need for `pip compile`, `pip install`, etc.

### Typing

* Assume the latest pyright version
* Prefer modern typing: `list[str]` over `List[str]`, `dict[str, int]` over `Dict[str, int]`, etc.
* Prefer to keep typing errors in place than eliminate type specificity:
  * Do not add ignore comments such as `# type: ignore`
  * Never add an `Any` type.
  * Do not `cast(object, ...)`

### Data Manipulation

* Prefer `funcy` utilities to complex list comprehensions or repetitive python statements.
* `import funcy as f` and `import funcy_pipe as fp`
* Some utilities to look at: `f.compact`

For example, instead of:

```python
params: dict[str, str] = {}
if city:
    params["city"] = city
if state_code:
    params["stateCode"] = state_code
```

Use:

```python
params = f.compact({"city": city, "stateCode": stateCode})
```

### Date & DateTime

* Use the `whenever` library for datetime + time instead of the stdlib date library. `Instant.now().format_iso()`
* DateTime mutation should explicitly opt in to a specific timezone `SystemDateTime.now().add(days=-7)`

<!-- END CLONED INSTRUCTIONS -->
