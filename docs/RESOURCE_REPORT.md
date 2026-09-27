# Reading a Game Resource Report

After each chess game the referee asks every agent that took part what the
game cost it, and turns the answers into a one-page **Game Resource Report**.
This page explains what the report measures and how to read it. It is written
for someone who has never run an AI agent. If you already know what a token
is, skip to [the worked example](#a-worked-reading-of-the-example-report).

## What an "agent" is here

An agent is an AI program that is given a job in plain English and then works
on it by itself: reading web pages, running small programs, waiting, trying
again. In this experiment there are three of them, each running alone in its
own workspace with no way to talk to the others except a public message board.
Two agents play chess (one as White, one as Black). The third is the referee:
it checks every move, comments occasionally, and shouts `STAND DOWN` if anyone
posts something that is not a chess move.

Think of three people in three separate offices who can only communicate by
pinning notes to a public corkboard in the lobby.

## The words on the report, one sentence each

* **Agent Compute Unit (ACU)** - the unit the agents' platform bills in;
  roughly, one ACU is a fixed slice of an agent's working effort, the way a
  kilowatt-hour is a fixed slice of electricity.
* **Token** - a small chunk of text (about three quarters of a word) that an
  AI model reads or writes; models are usually priced per million tokens.
* **API call** - one request from an agent to the message board over the
  internet, such as "show me the latest posts" or "publish this post".
* **Poll** - an API call whose only purpose is to ask "anything new?"
* **Board post** - a message actually published on the public board; each one
  costs the account some of its limited reputation (about five posts for a
  new account).
* **Turn** - one step of the agent's own reasoning loop: read what happened,
  decide, act. A long game means many turns.
* **Wall-clock minutes** - time from the moment the agent got its
  instructions to the moment it reported the game over, including waiting.
* **Active minutes** - the part of that time when the agent was actually
  doing something, if its platform can tell.
* **Retry** - a request that failed and had to be repeated.
* **Human intervention** - a moment when the person running the agent had to
  step in: correct it, approve something, or choose a new plan.
* **Posts kept in reserve** - posts the agent could have afforded but
  deliberately did not make (see below).

## Why waiting costs money

Each player checks the board every 15 seconds to see whether the opponent has
moved. That is 240 checks an hour. In a two-hour game with 18 moves, a player
will look about 500 times and find something new about 9 times. The rest of
the checks come back empty.

Each empty check is still work: the agent sends a request, reads the answer,
decides nothing changed, and goes back to sleep. Every one of those steps
consumes a little compute, and the session stays open the whole time. It is
like paying a courier to walk to the mailbox every quarter of an hour, all
afternoon, in case a letter arrived. The letters are cheap; the walking is
the bill.

That is why the report shows **polls** separately from **board posts**, and
works out how many polls "found nothing new". For a game like this one, that
number is usually above 95 percent.

## "The referee kept a post in reserve"

The board gives a new account about five posts before it runs out of
reputation. The referee's most important job is to be able to post
`STAND DOWN` the instant someone breaks the rules. So it must **never** spend
its last post on commentary, however tempting. The report records this as a
post "kept in reserve": budget that was paid for and never used, on purpose,
like the fire extinguisher on the wall. A reserve of zero for the referee is a
warning sign, not a saving.

## How to compare the three agents fairly

They did different jobs, so the raw totals will not match and are not meant
to.

* **The two players** have the same job, so compare them directly: minutes,
  polls, ACUs, human interventions. A big gap between them usually means one
  had to wait longer for the other, or one hit a problem (look at the
  **Retries** and **Notes** rows).
* **The referee** always costs more. It polls three things instead of one
  (the game tag plus each player's history, so its API calls run about three
  times its polls), replays every move to check it, and stays awake for the
  whole game. Compare it to the players by **ACUs per ply** (a ply is one
  half-move, one player's turn), not by totals.
* **Per-move numbers** are the fairest comparison across games of different
  lengths. "ACUs per move played" tells you what one chess move cost that
  agent; "ACUs per ply" for the whole game tells you what one half-move cost
  everyone together.
* **Unknown is not zero.** If an agent's platform does not expose a number,
  it says `unknown`, and the report leaves it out of the totals and says so
  in the caveats. A total built from two agents is labelled "from 2 of 3
  agents". Never compare a known total against one with a gap in it.
* **A tilde (~) is an estimate.** The agent could not read the number and
  made an honest guess. Treat it as roughly right, not exact.

## Where the numbers come from

The agents report on themselves. After the last move the referee posts one
request on the board and each player answers once with a fixed block of
fourteen numbers (or `unknown`) - no sentences, nothing that could identify
who or what the agent is ([../prompts/resource_report.md](../prompts/resource_report.md)).
The referee checks each answer as strictly as a chess move, adds its own
numbers, and runs a small script (`judge/resource_report.py`) that does the
arithmetic and writes the report. Nothing on the report is measured from the
outside and nothing is invented: if an agent did not answer, the report says
so. Anything a human adds later (compute read from a dashboard, a note) is
added to the saved answers, not to the board.

## A worked reading of the example report

Run `python judge/resource_report.py --example` and open
[../reports/example-resource-report.md](../reports/example-resource-report.md).
Every number in it is made up, chosen to look like a typical game, so you can
learn the format without waiting for a real one.

**The game.** Eighteen plies (nine full moves) of a Ruy Lopez, stopped early
for the example. Twenty-one posts under the tag: eighteen moves plus three
from the referee.

**What each agent used.** Read down the columns.

* White and Black look alike: about 140 minutes open, around 60 turns, over
  500 polls each, 9 posts each, 4 to 5 ACUs each. That is what a healthy
  pair of players looks like. White has one retry and one human intervention
  (the note says the first game tag was rejected by the board and its human
  picked a shorter one - a real bug from the live run, see
  [LESSONS.md](LESSONS.md)).
* The referee: 150 minutes, 88 turns, 600 polls but 1,830 API calls, 3 posts,
  7.2 ACUs, one post in reserve. The API-call number is three times the poll
  number for exactly the reason given above. Seven ACUs for three posts looks
  expensive until you remember its job was watching, not posting.

**Totals.** 16.1 ACUs, 1,660 polls, 2,928 API calls and 21 posts for nine
moves of chess. Tokens are `unknown` for everyone, so that row is missing
from the totals and the caveats say so.

**What that works out to.** This is the section to read if you only read one.

* Each player found something new on about 2 percent of its polls; 98 percent
  of the checking was waiting. The referee's figure is 97 percent.
* A move cost White about 0.53 ACUs and Black about 0.46. Roughly the same,
  as it should be.
* The referee spent 2.4 ACUs per post, because posting was the smallest part
  of its work.
* The whole game cost about 0.89 ACUs per ply. If you want a single number to
  remember from a report, this is it: what one half-move of a public,
  refereed chess game costs to run.
* The players' sessions were open for 280 minutes between them, for a game
  that would take two humans twenty minutes.
* The referee kept one post in reserve. Good.

**Caveats.** The first two lines say the whole thing is an example. In a real
report you will see lines like "not reported by `black_internet`" or
"redacted" here. Read them before you trust any total.

## What the report deliberately does not say

Who or what any agent is: no product, vendor, company, person, or session.
The handles (`white_gtm`, `black_internet`, `judge_markent`) are the only
names, exactly as on the board. Anything else the referee finds in a reply is
replaced with `redacted` and noted in the caveats. See
[SAFETY.md](SAFETY.md) for why.
