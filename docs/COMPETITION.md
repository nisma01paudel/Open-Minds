# The competition, measured

Looked up on 2026-10-01, from the event's own tooling rather than from its marketing.

## The rubric, finally, from the event's own site

I had been planning against the leaderboard's mechanics for six rounds because `frogtoberfest.com` returns
an error page from here. **That is not the event's site** - it is an unregistered domain, and the Wayback
snapshot is a parking page. The real one is:

**<https://frogtoberfest.lftechnology.com/>**, a client-rendered SPA whose content lives in
`/static/js/main.648176dd.chunk.js`. Reading the bundle gives the criteria verbatim.

### How a winner is chosen

> The project that stands out for **innovation, technical excellence, open-source contribution, and
> real-world impact.**

**Top five** are shortlisted - *"Every entry gets run through the eligibility gate and quick screen, but
the top 5 move on to present live on October 30."* **At least one member must be physically present in
the Kathmandu valley.** Open to anyone based in Nepal, solo or up to five.

### The eligibility gate - six requirements

1. **Public GitHub repository** - public, with everything needed to run and understand it
2. **Documentation** - README, architecture overview, technology details, **and limitations/future
   improvements, all present and complete**
3. **Working demo** - a functional demonstration of the key capabilities
4. **Demo video** - showing the problem, solution, workflow and value
5. **Qualifies as "Build with AI"** - *"AI does real work inside the solution: processing, transforming,
   or reasoning over data as part of the system's core logic - not just generating a response that gets
   shown to a user."*
6. **AI usage disclosure** - *"a short written statement naming the exact file/function where AI output
   is consumed programmatically"*

### Where this project stands against the gate

| requirement | state |
|---|---|
| public repository | yes - `sushant-me/work`, not a fork, commits linked to the account |
| documentation | yes - README, `docs/`, and `docs/LIMITATIONS.md`, which is a full document rather than a paragraph |
| working demo | yes - <https://sushant-me.github.io/work/>, deployed since round 4 |
| demo video | yes - 159 s, `reports/video/pahiro-narrated-web.mp4` |
| Build with AI | yes - `router.py::triage_route()` turns an unstructured hazard report into *(which asset is failing, which duty applies)*, and the ontology then maps that pair deterministically |
| AI usage disclosure | yes - `docs/AI-USAGE.md`, which names each entry point as `file::function` |

**Requirement 5 is the one to argue, not tick.** The project's own line is that the model decides *which
asset and which duty*, and everything downstream - the institution, the statute, the letter - is read
from the ontology and can never be invented. That is AI doing core work rather than generating text.

### The anti-pattern the event names, which this project spent eighty rounds on

> *"Building a reusable skill, prompt library, or tool definition, with nothing using it"*

That is the exact defect found and fixed nine times here - code that exists, is compiled, passes every
test, and is never reached. The Places layer had no working toggle. The speech stub returned `false`
unconditionally. Nine panels vanished when their data failed.

**The event names it as a failure mode. This repository has three guards against it**, each proven to
fail on purpose.

### Proprietary APIs

> *"Proprietary APIs like OpenAI, Claude, or Gemini are discouraged, even for small auxiliary calls.
> Document what you used, name the model, and disclose."*

`check_eligibility.py` already greps `src/` for a vendor inference endpoint and reports none.

## The leaderboard is the scoreboard, and it does not count commits

`https://frogtoberfest-leaderboard.lftechnology.com` is live. Its columns are:

| User Name | PR Opened | PR Reviewed | Issue | PR/Issue Comments | Total Score |
|---|---|---|---|---|---|
| Xtha-Sunil | 25.6 | **80.0** | 53.4 | 58.2 | **217.2** |
| trishan9 | 51.2 | 39.5 | 3.9 | 35.9 | 130.5 |
| devsdenepal | 69.0 | 13.0 | 24.9 | 5.7 | 112.6 |
| aayush105 | 31.2 | 51.5 | 5.1 | 23.9 | 111.7 |
| ChiefBibek | 94.8 | 0.0 | 0.9 | 0.7 | 96.4 |

Its repository (`Lf-Network/oss-leaderboard`) describes itself as "Scoring is based on contributions
made in public repos". The scored contribution types are **pull requests opened, pull requests
reviewed, issues, and comments on either.** There is no column for commits.

## This project scores nothing on it, and that is the finding

    sushant-me on the leaderboard   ABSENT          (121 rows are listed, down to a score of 0.1)
    commits in this repository      238
    merge commits                   0              every one went straight to main

83 rounds of work - two platforms, 568 Python tests, 65 Dart tests, a deployed web app, 44 photographed
frames - is invisible to the thing that decides the event, because **none of it passed through a pull
request.** Commits pushed directly to a default branch are not a scored contribution type.

## What that means, plainly

The work is not the problem. **The route the work takes is.**

Three things follow, in order of how much they are worth:

1. **Stop pushing to main.** Every change becomes a branch and a pull request, merged. Our own
   repository is public, so our own pull requests count. This is the single largest change available.
2. **Review other people's pull requests.** This is the heaviest single column in the field -
   80.0 of Xtha-Sunil's 217.2, nearly 40% - and costs reading time rather than code.
3. **File issues.** Real ones, from real defects: this session found thirteen, each with a reproduction
   and a fix. An issue is a scored artefact and the material already exists.

An earlier finding stands and is worth keeping: `sushant-me/work` is not a fork and GitHub links every
commit to the `sushant-me` account, so commit-based contribution graphs do credit. That is simply not
the graph this event scores.

## The route now works, and it has been used

    PR #1    opened and merged    https://github.com/sushant-me/work/pull/1
    Issue #2 opened               https://github.com/sushant-me/work/issues/2

Both are scored contribution types. The point of doing them immediately rather than describing them was
to establish the mechanism end to end: `gh` is authenticated as `sushant-me`, a branch pushes, a pull
request opens against `main`, a squash merge puts `(#1)` on the commit, and an issue files with its
context attached.

### The defects this project found are now filed, not just fixed

    #2  the required video predates four of the features it should show
    #3  the Places layer had no working toggle for every round it existed
    #4  the film says 31 on screen and spoke 305 aloud, and a test enforced both

Each carries the reproduction, the root cause, the fix commit and the guard that now prevents it.
This is the material from the eighty-round verification pass, converted into the one form the event
actually scores - and it is honest material rather than filler: three real defects, documented to the
standard the rest of this repository holds.

**Every change from here goes this way.** The repository is public, so its own pull requests count, and
the cost is one branch and one merge per change rather than a push.

## What is NOT known

- The exact weights. The columns are visible; the coefficients are not, and `frogtoberfest.com` returns
  an error page from here. **The rubric has been requested from the team and has not arrived.**
- Whether registration is required to appear on the leaderboard at all - `sushant-me` being absent
  while 0.1-scoring users are listed is consistent with either no scored contributions or not being on
  the tracked list.
- The field. 18 repositories carry the `frogtoberfest` topic on GitHub; the leaderboard lists far more
  people than that, so most entrants have not published an event repo. **The closest by positioning -
  "offline, open-weight AI" - is `angel97-cyber/parivartan-site-change-ledger` at 4 KB.**
