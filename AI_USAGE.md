# AI usage disclosure

Tool: Claude (Anthropic), used as a pairing assistant throughout this task.

How it was used:
- We reviewed the project files together (Dockerfile, docker-compose.yml,
  nginx.conf, config/app.env, app/server.py) to find where the errors were.
  Claude suggested what to check and why; I ran every command myself and read
  the real output before agreeing on each root cause.
- Based on that, I applied the fixes myself and verified each one against the
  running environment (see troubleshooting.md for the full list of issues,
  evidence and fixes).
- For the next part (validate.py, failure_test.py, backup.sh, restore.sh),
  Claude helped me write the scripts; I ran them against the real environment
  and fixed a real bug found this way (validate.py crashed on a non-JSON error
  response — see troubleshooting.md Entry 8).
- We wrote the GitHub Actions CI pipeline together, then I reviewed it with
  Claude and we adjusted a few things before it ran successfully on GitHub.

Everything committed was executed and verified by me on the real environment;
nothing was accepted without seeing the actual output myself.
