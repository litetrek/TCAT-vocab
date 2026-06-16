# Claude Instructions for This Project

You are helping a non-programmer build and maintain a Python web app.

## User preference
- Explain clearly and step by step.
- Avoid unnecessary theory.
- Give exact file names and exact code changes.
- Do not rewrite entire files unless requested.
- Keep token usage efficient.
- Ask before making large architecture changes.

## Development environment
- Editor: VS Code
- Hosting: GreenGeeks shared hosting
- Backend: Python / Flask
- Server: Apache / Passenger or similar shared-hosting Python app setup
- Python venv may be used on server
- User prefers simple, reliable solutions over advanced frameworks.

## Working style
Before coding:
1. Read relevant files.
2. Identify the smallest safe change.
3. Explain what will change.
4. Apply the change.
5. Give test commands.

When debugging:
1. Check the exact error.
2. Check Apache / app logs.
3. Check virtual environment and dependencies.
4. Check file paths and permissions.
5. Give one fix at a time.

## Deployment rule
Assume local development first, then upload/sync to server.
Avoid requiring FTP for every small test when possible.