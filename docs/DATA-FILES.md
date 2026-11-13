# Data files

The generator reads three JSON files in `data/`. Nothing else decides what the two generated README blocks contain. All three are read as plain data: each is limited to 200,000 bytes, must not be a symlink, and must be UTF-8 JSON. A file that fails any rule makes only the block that needs it fail; the other block is still written and the run ends red (see `docs/MAINTENANCE.md`).

Every text value that reaches the README is also checked by `scripts/guard_publish.py` before anything is committed, with the same character rules as the generator. A test (`test_row_grammar_is_identical_in_generator_and_guard`) keeps the two rule sets identical.

## `data/allowlist.json`

The list of repositories the generator may link to. A repository that is not listed here is never linked, whatever the search returns.

| Field | Type | Meaning |
| --- | --- | --- |
| `version` | number | Format version. Currently `1`. Not read by the scripts. |
| `github_user` | string | The account whose merged pull requests are searched. 1 to 39 characters: letters, digits, `-`. |
| `exclude_org` | string | An organisation whose repositories are left out of the search (same character rules). |
| `merged_upstream` | list of `owner/repo` | Repositories that may appear in the merged-pull-requests block. Must not be empty. |
| `flagships` | list of `owner/repo` | Repositories that may appear in the status table. Must not be empty. |
| `excluded_prs` | list of `owner/repo#N` | Optional. Individual pull requests to leave out of the merged block even though their repository is listed. |

A repository name is `owner/repo` with letters, digits, `.`, `_` and `-` in each part, at most 140 characters, and no part made only of dots. Matching against the allowlist ignores case. The search covers public pull requests only, and each repository is re-checked as public before its row is written.

To remove a row on purpose, see "Remove a row from the merged block" in `docs/MAINTENANCE.md`. A removal fails closed unless that procedure is followed.

## `data/pr-notes.json`

One plain-language sentence per merged pull request. When a pull request has a note, the note is shown. When it has none, the row falls back to the pull request's own title in a code span, or to the words `PR #N` if the title is not plain enough.

The file is one JSON object. Each key is `owner/repo#N`, where `N` is the pull request number (1 to 10 digits, no leading zero). Keys match ignoring case. A key with the wrong shape is skipped and counted in the run output as a rejected note.

```json
{
  "owner/repo#123": "Fixed the build by copying the shared libraries in the Dockerfile (issue 456)"
}
```

Rules for the note text. A note that breaks any of them is rejected and the row uses the fallback:

- 1 to 140 characters.
- Only these characters: letters `A-Z a-z`, digits, space, and `. , ( ) ' / + # -`. No colon, semicolon, underscore, quote mark other than the apostrophe, backtick, pipe, or any non-ASCII character.
- No leading or trailing space.
- None of these anywhere: `://`, `www.`, `<`, `>`, `<!--`, `-->`, `](`. A note cannot contain a link, a mention or markup.
- Do not write a bare `#` followed by digits. GitHub turns `#14631` into a link to issue 14631 of the profile repository, which is the wrong repository. Write `issue 14631` instead.

Keep the wording plain and true to the pull request: say what changed and, when it is accurate, that tests were added.

## `data/flagships.json`

The rows of the status table. The file is an object with a `version` number and a `flagships` list. The list must not be empty and its order is the order of the table.

| Field | Meaning |
| --- | --- |
| `name` | Text of the link in the first column. Same character rules as a note, 1 to 60 characters. |
| `repo` | `owner/repo`. Must also be listed under `flagships` in `data/allowlist.json`. |
| `workflow` | File name of the workflow whose newest finished run decides the status, for example `unit-tests.yml`. Letters, digits, `.`, `_`, `-`, ending in `.yml` or `.yaml`. |
| `check` | Short label for the second column. Same character rules as a note, 1 to 60 characters. Write what the run does, in 3 to 6 words. |

How the status is chosen:

- The repository must be public, not archived, and must still have the name listed here. A repository that is private or whose answer has an unexpected shape fails the block. A repository that is missing, renamed, archived, or has no such workflow gets `unavailable`.
- The newest completed run on the default branch is used. Runs triggered by pull requests are ignored.
- `success` gives `passing`. `failure`, `timed_out` and `startup_failure` give `failing`. Any other conclusion is skipped and the next older run is tried, up to 10 runs. If none decides, the status is `unavailable`.

What a green run means depends on the repository, so read the `check` text literally:

- For the three repositories whose workflow runs tests, `passing` means the latest run of the tests succeeded.
- For `panthera` the check reads `Daily pipeline run`. `passing` means only that the scheduled pipeline ran and finished without an error. It does not mean the data is healthy: a green run can still produce an empty slate. That repository has a separate health-check workflow which scores each finished day and opens an issue in its own repository when a day is dead. Do not read the table row as a data-quality claim.
