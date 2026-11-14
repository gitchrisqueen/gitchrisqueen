# Maintenance guide

This page is for the owner of this profile repository. It explains how the automation works, what must be true before it runs, how to check that it is healthy, and what to do when it is not. Every command can be pasted as written. Replace `<run-id>` and `<sha>` where shown.

## Where to run these commands

Run them from a clone of `main`, or from anywhere if you keep the `--repo gitchrisqueen/gitchrisqueen` flag that every `gh` command here carries. A `git` command that needs a clone is written for the clone's own folder; from another folder use `git -C <clone>` instead. Run `gh auth setup-git` once before any `git push`, so that `git` uses the same credential as `gh`. The seed step in the first-run checklist works in a scratch clone of its own and ends with `cd ..` to get back out of it.

## How it works

Three workflows live in `.github/workflows/`.

| Workflow | Runs | What it does | Writes to |
| --- | --- | --- | --- |
| `ci.yml` | every pull request and every push except a push to the `output` branch, no path filter | offline tests, `actionlint`, SVG lint, colour-contrast check, supply-chain and wording checks, a read-only dry run of the generator and of the snake | nothing (uploads artifacts only) |
| `profile.yml` | daily at 06:23 UTC, on manual dispatch, and on a push to `main` that touches `scripts/**`, `data/**` or the workflow file | refreshes the two generated blocks in `README.md` | `README.md` on `main` |
| `snake.yml` | daily at 05:37 UTC, on manual dispatch, and on a push to `main` that touches `scripts/**`, `data/**` or the workflow file | draws the contribution-calendar snake (it grows as it eats active days) and its still-image twins | four SVG files on the `output` branch |

The two writer workflows share one shape:

1. `generate-text` (profile) or `generate-snake` (snake) has read-only access. It builds the new content, checks it, and uploads it as an artifact. The snake generator is this repo's own `scripts/make_growing_snake.py` (standard library only); it reads the contribution calendar with the read-only token and fails the run on any malformed value. No third-party action is used.
2. `publish` is the only job that can write. It runs only on `main`, downloads the artifact, checks it again with the scripts that are on `main`, copies only the named files, and commits as `github-actions[bot]`. It executes nothing from the artifact. If generation failed, `publish` still commits any block that was good, then fails the run on purpose.
3. `report` runs only when the run failed. It opens one issue for its own workflow, or updates the one that is already open. The body is fixed text: workflow, stage, which generated block failed, run link.
4. `close` runs only after a fully clean run and closes that workflow's open issue.

Rules that hold everywhere:

- Every workflow starts with `permissions: {}`. Each job asks for the least it needs: `contents: read` to generate, `contents: write` to publish, `issues: write` to report or close. No job holds both write scopes.
- Writers are serialised: `profile-main` for `main`, `output-branch` for `output`, both with `cancel-in-progress: false`. Nothing force-pushes.
- On any ref other than `main` the writer workflows are dry runs: they build and upload, and write nothing.
- The README keeps two generated blocks, between `<!-- MERGED-UPSTREAM:START -->` and `<!-- MERGED-UPSTREAM:END -->`, and between `<!-- FLAGSHIPS:START -->` and `<!-- FLAGSHIPS:END -->`. The guard (`scripts/guard_publish.py`) rejects any change outside those markers, any row that does not match the exact row format, any link that is not on `github.com`, and any repository that is not in `data/allowlist.json`.
- Hand edits inside the markers are overwritten by the next run. Change the data files (`data/allowlist.json`, `data/pr-notes.json`, `data/flagships.json`; the formats are in `docs/DATA-FILES.md`) or the text outside the markers instead.
- No daily timestamp is written to `main`, so the history only moves when the data does.
- A green row in the status table means the named check ran and passed, nothing more. For `panthera` the check reads `Daily pipeline run`: green means the pipeline ran, not that the data is healthy. That repository has its own health-check workflow, which files an issue there when a day's data is dead; read that, not this table, for data health. Details are in `docs/DATA-FILES.md`.

Two things about `ci` that are not obvious:

- Its dry run of the generator reads the live GitHub API, the same way the daily run does. An API outage or a rate limit can therefore turn `ci` red on a change that is correct. Re-run the failed job once the API answers; a re-run fixes it. A red `ci` that stays red on a re-run is a real problem.
- It skips pushes to the `output` branch, because that branch holds only the four SVG files and has none of the repository's code, so a run there could only fail. Every other push and every pull request runs `ci`, with no path filter.

Cost: the repository is public and every job uses a standard GitHub-hosted runner, which costs nothing. If the repository were ever made private, the minutes would count against the account's Actions quota, and the schedule and the timeouts would need a second look.

To run the offline tests locally:

```
python -m pip install --require-hashes --only-binary=:all: -r requirements-ci.txt
python -m pytest tests -q
```

## Prerequisites, with a check for each

Run these once before the first run, and again after any settings change. The expected result is in the last column.

| Prerequisite | Check | Expect |
| --- | --- | --- |
| Actions are enabled | `gh api repos/gitchrisqueen/gitchrisqueen/actions/permissions --jq '{enabled, allowed_actions}'` | `enabled` is `true` |
| Allowed actions include what the workflows use | `gh api repos/gitchrisqueen/gitchrisqueen/actions/permissions/selected-actions` (only meaningful when `allowed_actions` is `selected`) | a pattern for `actions/*` only; every action is pinned by full commit SHA |
| Issues are enabled | `gh repo view gitchrisqueen/gitchrisqueen --json hasIssuesEnabled --jq .hasIssuesEnabled` | `true` (if `false`, the report and close jobs do nothing, so failures raise no issue) |
| You are watching Issues for this repository | `gh api repos/gitchrisqueen/gitchrisqueen/subscription --jq '{subscribed, ignored}'` | `subscribed` is `true` and `ignored` is `false`. A 404 means you are not watching. The command cannot show which events you get, so open the Watch menu on the repository page and choose All activity, or Custom with Issues ticked. A failure issue notifies only people who watch Issues; if nobody does, a failed run is silent |
| Labels exist | `gh label list --repo gitchrisqueen/gitchrisqueen --search profile-automation` | both labels below are listed |
| The push credential holds the right scopes | `gh auth status` | account `gitchrisqueen`; scopes include `repo` and `workflow` (a fine-grained token needs Contents, Workflows, Issues and Actions write) |
| That credential can push | `gh api repos/gitchrisqueen/gitchrisqueen --jq .permissions.push` | `true` |
| No ruleset blocks the publish job | `gh api repos/gitchrisqueen/gitchrisqueen/rulesets --jq '.[] \| [.name, .enforcement] \| @tsv'` and `gh api repos/gitchrisqueen/gitchrisqueen/branches/main/protection` | no ruleset or protection that requires status checks or pull requests on `main` (a 404 from the second command means no classic protection) |
| The rollback tag exists | `git ls-remote --tags origin profile-v1-pre` | one line whose SHA starts with `0eb9533` |

Create the labels (the report job also tries to create its own label, but do it once by hand so the check above passes):

```
gh label create "profile-automation:profile" --repo gitchrisqueen/gitchrisqueen --color B60205 --description "Automated profile maintenance failures"
gh label create "profile-automation:snake" --repo gitchrisqueen/gitchrisqueen --color B60205 --description "Automated profile maintenance failures"
```

Notes on the credential:

- It is the owner's own credential on the machine that pushes the branch, the tag and `output`. There is no fork, so no first-time-contributor approval step applies. If a fork were ever used, the owner approves the first run.
- `git push --dry-run origin HEAD:refs/heads/scope-check` from a branch that changes a workflow file shows that the remote is reachable, but it does not test the `workflow` scope. The real proof is the first push of the branch that adds the workflow files: without the scope, GitHub refuses it with a message that names the workflow files.
- The weekly check under Monitoring uses a separate read-only token (set through `GH_TOKEN` for that block only), never this one.

Warning: a ruleset requiring status checks or PRs on main breaks the publish job. The publish job pushes straight to `main`. A ruleset that only blocks force-pushes and branch deletion is fine and recommended. Separately, in the repository's Actions settings it is sensible to restrict actions to the selected list, require full-SHA pinning, and require approval for outside collaborators. Update the selected list whenever a Dependabot bump changes a pin (see Dependabot below).

## Colour pairs and ratios

Every colour pair is declared in `assets/colors.json`: the text and background of the header and footer, the three badges in each state, and the contribution-calendar cells against their own opaque background. That file owns the values, so they are not copied here. To see the ratios:

```
python scripts/check_contrast.py assets/colors.json
```

The script fails below 4.5:1 for text pairs and below 3:1 for graphics pairs. The empty-day level of the calendar is exempt from the 3:1 rule because it carries no information. CI runs the same command on every push.

The calendar colours live only in `assets/colors.json`; `scripts/make_growing_snake.py` reads them from there. If you change a colour, edit that file, then run `python scripts/check_contrast.py assets/colors.json`.

The card, tool-logo and loop and terminal graphics (`assets/card-*.svg`, `assets/skills-*.svg`, `assets/loop-*.svg`, `assets/terminal-*.svg`) are built by `python scripts/build_assets.py` from the text inside that script and `data/icons.json` (logo paths from simple-icons, CC0). Edit the script, rebuild, commit the SVGs; CI fails with `out of date` if a committed SVG differs from the build. To add a logo, copy its path from the simple-icons package into `data/icons.json`.

## First-run checklist

### Before the pull request is merged

1. Confirm the rollback tag: `git rev-parse profile-v1-pre` prints a SHA that starts with `0eb9533`, and `git ls-remote --tags origin profile-v1-pre` shows the same SHA.
2. Wait for the `ci` check on the draft pull request to go green. In its run, open the `ci-dry-run` artifact and read `README.diff`: it is what the generator would change today. Open the four files in the `snake-artifacts` artifact in a browser once: the two `snake-static-*` files are the still-image twins and should show the full calendar with the snake at its start.
3. Seed the `output` branch so that no image is broken at merge time. The steps work in a scratch clone and keep the seed files outside it. Start in an empty working folder, not inside any clone. The first command writes `seed/` there, the clone is made beside it, and the last line, `cd ..`, returns you to the working folder:

```
gh auth setup-git
run_id=$(gh run list --repo gitchrisqueen/gitchrisqueen --workflow ci.yml --branch feat/profile-overhaul --status success --limit 1 --json databaseId --jq '.[0].databaseId')
gh run download "${run_id}" --repo gitchrisqueen/gitchrisqueen -n snake-artifacts -D seed/
git clone https://github.com/gitchrisqueen/gitchrisqueen.git profile-seed
cd profile-seed
git checkout feat/profile-overhaul
python scripts/lint_svg.py --profile chart --require-opaque-background --min-bytes 5000 --max-bytes 1500000 --expect rect=100 ../seed/*.svg
wc -c ../seed/*.svg
sha256sum ../seed/*.svg
git checkout --orphan output
git rm -rf .
cp ../seed/*.svg .
git add *.svg
git commit -m "chore: seed snake assets"
git push origin HEAD:refs/heads/output
cd ..
```

   Record the `sha256sum` output in the pull request body.

4. Check that every raw URL answers:

```
for f in snake.svg snake-dark.svg snake-static-light.svg snake-static-dark.svg; do
  echo "== ${f}"
  curl -sI "https://raw.githubusercontent.com/gitchrisqueen/gitchrisqueen/output/${f}" | grep -iE '^(HTTP|content-type|content-length)'
done
```

   Expect `200` and an image content type for each of the four. Write down what you actually see. Do not merge if any file is not `200`.

### After the pull request is merged

Every drill below dispatches a run, and dispatching returns before the run exists. So each one waits, finds the run it started, watches it to the end, and only then checks results. Read results only after the watch has returned. Before reading any result, confirm that the run you watched is the one you started: its `event` must be `workflow_dispatch`, and its `createdAt` must not be earlier than the time you noted before dispatching (allow a few seconds of difference between your clock and GitHub's). The merge itself also starts runs on `main`, so the newest run is not always yours; the `--event workflow_dispatch` filter in each command leaves those out. If the event or the time is wrong, the dispatch did not register yet: wait 15 seconds and run the lookup again.

5. Both writer workflows also fire once on the merge push. Start one run of each by hand as well, so the result does not depend on that trigger:

```
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
gh workflow run profile.yml --ref main --repo gitchrisqueen/gitchrisqueen
sleep 15; id=$(gh run list --repo gitchrisqueen/gitchrisqueen --workflow profile.yml --event workflow_dispatch --limit 1 --json databaseId --jq '.[0].databaseId'); gh run watch "${id}" --repo gitchrisqueen/gitchrisqueen --exit-status || true
gh run view "${id}" --repo gitchrisqueen/gitchrisqueen --json event,createdAt,status,conclusion --jq '[.event, .createdAt, .status, .conclusion] | @tsv'; echo "dispatched after ${started}"
gh workflow run snake.yml --ref main --repo gitchrisqueen/gitchrisqueen
sleep 15; id=$(gh run list --repo gitchrisqueen/gitchrisqueen --workflow snake.yml --event workflow_dispatch --limit 1 --json databaseId --jq '.[0].databaseId'); gh run watch "${id}" --repo gitchrisqueen/gitchrisqueen --exit-status || true
gh run view "${id}" --repo gitchrisqueen/gitchrisqueen --json event,createdAt,status,conclusion --jq '[.event, .createdAt, .status, .conclusion] | @tsv'
gh run list --repo gitchrisqueen/gitchrisqueen --limit 6 --json workflowName,event,status,conclusion,databaseId
```

   Expect each line printed after a watch to show `workflow_dispatch`, a time after the one printed, `completed` and `success`. A new commit appears on `output` (`gh api repos/gitchrisqueen/gitchrisqueen/commits/output --jq .commit.message` prints `chore: refresh snake assets`), the four raw URLs from step 4 still answer `200`, and the profile page renders the images. If the snake files did not change since the seed, the run is green and adds no commit; the publish log then says so.

6. Fault-injection drill for the text workflow. Dispatch, wait, watch, then check:

```
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
gh workflow run profile.yml --ref main -f inject_fault=bad-allowlist --repo gitchrisqueen/gitchrisqueen
sleep 15; id=$(gh run list --repo gitchrisqueen/gitchrisqueen --workflow profile.yml --event workflow_dispatch --limit 1 --json databaseId --jq '.[0].databaseId'); gh run watch "${id}" --repo gitchrisqueen/gitchrisqueen --exit-status || true
gh run view "${id}" --repo gitchrisqueen/gitchrisqueen --json event,createdAt,status,conclusion --jq '[.event, .createdAt, .status, .conclusion] | @tsv'; echo "dispatched after ${started}"
gh run view "${id}" --repo gitchrisqueen/gitchrisqueen --json jobs --jq '.jobs[] | [.name, .conclusion] | @tsv'
gh issue list --repo gitchrisqueen/gitchrisqueen --label "profile-automation:profile" --state open --json number,title
```

   Expect: the run ends `failure`; `generate-text` is `failure`, `publish` is `failure` (its last step fails on purpose, after committing any good block), `report` is `success`, `close` is `skipped`; exactly one open issue. The other block was still written: if it had new data, a `chore: refresh profile data` commit is on `main`, and no row from the bad entry is.

   Run the same block again. Expect the same single issue, with a new "Last update" line and no second issue.

   Cross-check that the labels are independent. With the profile issue still open, dispatch a clean snake run, wait for it to finish, and only then confirm the profile issue is still open:

```
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
gh workflow run snake.yml --ref main -f inject_fault=none --repo gitchrisqueen/gitchrisqueen
sleep 15; id=$(gh run list --repo gitchrisqueen/gitchrisqueen --workflow snake.yml --event workflow_dispatch --limit 1 --json databaseId --jq '.[0].databaseId'); gh run watch "${id}" --repo gitchrisqueen/gitchrisqueen --exit-status || true
gh run view "${id}" --repo gitchrisqueen/gitchrisqueen --json event,createdAt,status,conclusion --jq '[.event, .createdAt, .status, .conclusion] | @tsv'; echo "dispatched after ${started}"
gh issue list --repo gitchrisqueen/gitchrisqueen --label "profile-automation:profile" --state open --json number,title
```

   Expect a green snake run and the profile issue still listed. Then dispatch a clean text run and confirm the run is green and the issue is closed:

```
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
gh workflow run profile.yml --ref main -f inject_fault=none --repo gitchrisqueen/gitchrisqueen
sleep 15; id=$(gh run list --repo gitchrisqueen/gitchrisqueen --workflow profile.yml --event workflow_dispatch --limit 1 --json databaseId --jq '.[0].databaseId'); gh run watch "${id}" --repo gitchrisqueen/gitchrisqueen --exit-status || true
gh run view "${id}" --repo gitchrisqueen/gitchrisqueen --json event,createdAt,status,conclusion --jq '[.event, .createdAt, .status, .conclusion] | @tsv'; echo "dispatched after ${started}"
gh issue list --repo gitchrisqueen/gitchrisqueen --label "profile-automation:profile" --state open --json number,title
```

   Expect `success` and an empty list.

7. Fault-injection drill for the snake workflow. Record the branch tip first, before dispatching, then inject, wait, watch, and compare:

```
before=$(git ls-remote https://github.com/gitchrisqueen/gitchrisqueen.git refs/heads/output | cut -f1)
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
gh workflow run snake.yml --ref main -f inject_fault=bad-svg --repo gitchrisqueen/gitchrisqueen
sleep 15; id=$(gh run list --repo gitchrisqueen/gitchrisqueen --workflow snake.yml --event workflow_dispatch --limit 1 --json databaseId --jq '.[0].databaseId'); gh run watch "${id}" --repo gitchrisqueen/gitchrisqueen --exit-status || true
gh run view "${id}" --repo gitchrisqueen/gitchrisqueen --json event,createdAt,status,conclusion --jq '[.event, .createdAt, .status, .conclusion] | @tsv'; echo "dispatched after ${started}"
gh issue list --repo gitchrisqueen/gitchrisqueen --label "profile-automation:snake" --state open --json number,title
after=$(git ls-remote https://github.com/gitchrisqueen/gitchrisqueen.git refs/heads/output | cut -f1)
test "${before}" = "${after}" && echo "output unchanged"
```

   Expect: a red run that stops at the lint step, one open snake issue, and `output unchanged`. Then run the same dispatch, wait and watch with `inject_fault=none` in place of `bad-svg`, and expect a green run and, once it has finished, a closed issue.

8. Rehearse a purge of the image cache on one snake URL. GitHub serves images in a profile through a cache, and a bad image can outlive a fix until the cache is told to refetch. Read the cache URLs from the rendered page, then purge one:

```
curl -s https://github.com/gitchrisqueen | grep -oE 'https://camo\.githubusercontent\.com/[0-9a-f]+/[0-9a-f]+' | sort -u
curl -sS -X PURGE "<one of the URLs printed above>"
```

   Write down the reply. If the purge is refused, note that too; the cache then refreshes on its own schedule.

9. Check that the workflows are active: `gh api repos/gitchrisqueen/gitchrisqueen/actions/workflows --jq '.workflows[] | [.name, .state] | @tsv'`. Expect `active` for each.

10. Whether a push made by the workflow's own token counts as repository activity for the 60-day rule below is not verified. Do not rely on it.

### If the first run after the merge is red

Roll back in the order given under Rollback, in the same sitting. Do not leave a red first run in place.

## Monitoring and the 60-day rule

Nothing in this repository watches the workflows. There is no scheduled monitor and no alert for a workflow that stops running. The only automatic signal is the failure issue, which is opened when a run starts and then fails, and which reaches you only if you watch Issues for this repository (see the prerequisites). A workflow that never starts raises nothing: that covers `startup_failure`, a disabled workflow and a schedule that has stopped. So the weekly check below is a manual task owned by the repository owner. Put a recurring reminder of your own choosing in whatever calendar you already read, and do the check from it.

GitHub disables scheduled workflows in a public repository after 60 days without repository activity. The state then shows as `disabled_inactivity`. Whether a push by the workflow's own token counts as activity is not verified, so the weekly check looks for it. A problem can go unnoticed for up to 7 days by design.

The weekly check is read-only and runs on the owner's own machine. Use a separate read-only credential, never the push credential: a fine-grained personal access token limited to this one repository with Actions: read, Contents: read, Issues: read and Metadata: read, and no write permission. Keep it in an environment variable on that machine (for example in the shell profile or the system keychain), never in this repository. The block sets it once and then proves it cannot write:

```
export GH_TOKEN="${PROFILE_CHECK_TOKEN}"   # the read-only token, kept outside this repository
gh api repos/gitchrisqueen/gitchrisqueen --jq .permissions.push   # must print false; empty output also means stop
gh run list --repo gitchrisqueen/gitchrisqueen --workflow profile.yml --status success --limit 1 --json createdAt --jq '.[0].createdAt'
gh run list --repo gitchrisqueen/gitchrisqueen --workflow snake.yml --status success --limit 1 --json createdAt --jq '.[0].createdAt'
gh api repos/gitchrisqueen/gitchrisqueen/actions/workflows --jq '.workflows[] | [.name, .state] | @tsv'
gh api repos/gitchrisqueen/gitchrisqueen/commits/output --jq .commit.committer.date
gh issue list --repo gitchrisqueen/gitchrisqueen --state open --label "profile-automation:profile"
gh issue list --repo gitchrisqueen/gitchrisqueen --state open --label "profile-automation:snake"
date -u +%Y-%m-%dT%H:%M:%SZ
unset GH_TOKEN
```

If the first command prints `true` or nothing, stop: that token can write or is not in use, so check that `PROFILE_CHECK_TOKEN` is set (an unset variable makes `gh` fall back to the stored push credential) and replace the token before continuing. A fine-grained token expires, so note its expiry date in your reminder; an authentication error in this block usually means it lapsed. An open failure issue means a run failed and nobody has seen a clean run since, even if the Watch settings hid the notification.

Compare each time with the date printed on the last line. Act when:

- the last success of either workflow is older than 3 days (the schedules run daily);
- any workflow state is not `active`;
- the newest commit on `output` is older than 3 days and the last snake success is also old or missing. The publish job commits only when a snake file changed, so a quiet stretch with no new contributions can leave `output` untouched while everything is healthy.

To re-enable after a disable (this needs the owner's write credential, not the read-only token):

```
gh workflow enable profile.yml --repo gitchrisqueen/gitchrisqueen
gh workflow enable snake.yml --repo gitchrisqueen/gitchrisqueen
gh workflow run profile.yml --repo gitchrisqueen/gitchrisqueen --ref main
gh workflow run snake.yml --repo gitchrisqueen/gitchrisqueen --ref main
```

## Detection table

List recent runs with `gh run list --repo gitchrisqueen/gitchrisqueen --workflow profile.yml --limit 10 --json databaseId,event,conclusion,createdAt` (use `snake.yml` for the other one).

| What you see | What it means | Issue raised? | What to do |
| --- | --- | --- | --- |
| Run `failure`, `generate-text` or `generate-snake` red | the API, a block, or a check failed; nothing was published for the failed part | yes, one per workflow, updated on repeat (it notifies you only if you watch Issues) | open the run link in the issue; fix, then run the workflow by hand |
| Run `failure`, `publish` red | the guard refused the artifact, or the push failed five times | yes | read the guard message (rule names and line numbers only); a diff outside the markers is an incident, see below |
| `startup_failure` | the workflow file is invalid, or Actions settings block a pinned action (for example after a bump that the selected-actions list does not yet name) | no: no job started, so the report job cannot run; only the weekly manual check or a look at the Actions tab finds it | `gh run view <run-id> --repo gitchrisqueen/gitchrisqueen` and read the annotation; compare `selected-actions` with the pins |
| `cancelled` | someone cancelled the run, or a newer `ci` run replaced it (the writer workflows never cancel each other) | no | confirm it was intended; run the workflow again if not |
| A run that timed out (a job passed its `timeout-minutes`; the run may show `timed_out` or `cancelled`, so read the annotation) | a job hung | not reliably | run again; if it repeats, investigate the step that hung |
| Workflow state not `active` | disabled by inactivity or by hand | no: nothing runs, so nothing reports; only the weekly manual check finds it | re-enable with the commands above |
| Newest `output` commit older than 3 days while the last snake run is green | either a quiet stretch (the publish job commits only when a file changed) or the publish job is not reaching the push | no | read the latest `publish` job log; "nothing to commit" is normal on a quiet stretch |
| Issues disabled in the repository settings | report and close do nothing | no | enable Issues, see the prerequisites |
| Not watching Issues | the issue is opened but nobody is told | yes, but silent | set the Watch level, see the prerequisites |
| Dependabot pull request | a pin has a newer version | n/a | see Dependabot below |

## Rollback, in this order

1. Stop the writers so nothing races the repair. Disabling a workflow does not stop a run that has already started, so cancel those too:

```
gh workflow disable profile.yml --repo gitchrisqueen/gitchrisqueen
gh workflow disable snake.yml --repo gitchrisqueen/gitchrisqueen
gh run list --repo gitchrisqueen/gitchrisqueen --status in_progress --json databaseId,workflowName
gh run cancel <run-id> --repo gitchrisqueen/gitchrisqueen
```

   Run the cancel command once for each in-progress run listed, then run the list command again and expect an empty result.

2. Restore the README by a normal commit that puts the old content back. History is kept and nothing is force-pushed:

```
git fetch origin --tags
git checkout -b rollback/readme origin/main
git checkout profile-v1-pre -- README.md
git commit -m "revert: restore the previous profile README"
git push origin HEAD:refs/heads/main
```

   If a rule requires a pull request for `main`, push the branch and open one instead.

3. Fix the `output` branch by reverting the bad commit, so history stays intact:

```
git fetch origin output
git checkout -b fix/output origin/output
git log --oneline -5
git revert --no-edit <sha>
git push origin HEAD:refs/heads/output
```

   You can instead put known-good SVGs in a new commit on top. Delete `output` only if neither works, and only after steps 1 and 2. The image URLs never change, so the README needs no edit after `output` is fixed. Purge the image cache afterwards (checklist step 8).

4. When the cause is fixed, re-enable the workflows and run each once by hand.

## Incident runbook

An incident is any of: a change on `main` outside the generated blocks, text in a generated block that does not look like a plain row, an image that is not the expected snake, or a job log that shows an unexpected download or command.

1. Contain: disable both workflows and cancel their in-progress runs (Rollback step 1).
2. Assess: `git log -p -5 -- README.md` for text, `git log --stat -5 origin/output` for images, and the failing run's log. The guard output names the rule and line number, never the content.
3. Repair: Rollback steps 2 and 3, then purge the image cache.
4. Check the pins: `grep -rn "uses:" .github/workflows` must show only 40-character SHAs. If the snake generator is suspect, leave `snake.yml` disabled and drop the snake block from the README; the rest of the page does not depend on it.
5. Find the cause, fix it with a test, and re-enable.
6. Write what happened in the open issue before closing it.

Secrets: the repository has none, and the workflows use only the short-lived token GitHub issues to each run. There is nothing to rotate. If the owner's own login credential is ever suspected of exposure, revoke it in GitHub settings and sign in again with `gh auth login`. Owner: the repository owner. Target: the same day.

## Dependabot

`.github/dependabot.yml` opens weekly pull requests for the action pins and for `requirements-ci.txt`. Dependabot pull requests never merge on their own: there is no auto-merge, and `.github/CODEOWNERS` requests the owner's review. Before merging a bump, read the upstream change between the old and new commit, most of all for the snake generator, which is the only third-party action. After merging a bump that changes a pin, update the selected-actions list in the repository's Actions settings, then run `gh api repos/gitchrisqueen/gitchrisqueen/actions/permissions/selected-actions` to confirm it names the new SHA. Otherwise the next run ends in `startup_failure`.

## Changing what the workflows do

- Edit `.github/workflows/*.yml` through a pull request. `ci` runs `actionlint` and the structural tests in `tests/test_workflows.py`, which fail if a rule above is loosened: unpinned action, a new trigger, an expression inside a shell step, a missing timeout, a write job without the `main` gate.
- A change to `scripts/**`, `data/**` or a writer workflow file that lands on `main` triggers the matching workflow once.
- The generator can only link to repositories listed in `data/allowlist.json`. A new merge into an unlisted repository is ignored until a person adds it there.

## Remove a row from the merged block

Taking a pull request out of the merged block (an `excluded_prs` entry in `data/allowlist.json`, or a repository dropped from `merged_upstream`) makes the block shorter. That is blocked in two places on purpose, so a partial or broken answer from the API can never quietly delete rows:

- the generator ends the block with `shrunken result` and keeps the old content, and
- the guard fails with `fewer rows than the base`.

Both fail closed, so the daily run goes red and opens an issue until the README and the allowlist agree again. The one safe way through is a single reviewed commit that changes `data/allowlist.json` and the README block together. Both scripts have an explicit flag for this, `--allow-shrink`. It switches off only the fewer-rows check: an empty block, a bad row, a link off `github.com`, a repository outside the allowlist and any change outside the markers still fail. The scheduled workflows never pass the flag, and `tests/test_workflows.py` fails if the word appears in a workflow file.

1. In a clone of `main`, start a branch for the change. Edit `data/allowlist.json`: add `owner/repo#N` to `excluded_prs`, or remove the repository from `merged_upstream`.
2. Regenerate the README locally with the flag. The token is only used for read requests, and `--allow-non-ghs` is needed because a personal token does not start with `ghs_`:

```
GITHUB_TOKEN="$(gh auth token)" python scripts/update_profile.py --readme README.md --allow-shrink --allow-non-ghs
```

   Expect the line `shrink allowed by --allow-shrink` and `result: ok`. Run `git diff README.md` and confirm that only the rows you meant to remove are gone.

3. Run the guard on the same change, with the flag, against the README as it is on `main`:

```
git show origin/main:README.md > "${TMPDIR:-/tmp}/README.base.md"
python scripts/guard_publish.py --base "${TMPDIR:-/tmp}/README.base.md" --new README.md --allowlist data/allowlist.json --allow-shrink
```

   Expect `guard: ok`.

4. Commit `data/allowlist.json` and `README.md` together and open a pull request. `ci` runs the generator without the flag, against the README in the pull request, which already has the row removed, so it passes. After the merge the next scheduled run starts from the shorter block and also passes.

If only one of the two files is changed, the next run fails closed and opens an issue. That is the check working: put the two files back in step.

## Links in the README

The Connect list in the README points to the owner's own for-agents page. The page is owned and edited by the owner. Review its text each time it changes: it should state facts and links only, and must not contain instructions addressed to a model.
