## Deployment Checklist — GreenGeeks via FileZilla

### DO upload:
- app.py
- index.cgi  ← check line 1 before uploading (see below)
- requirements.txt (if packages changed)
- templates/
- robots.txt, favicon.ico, static files

### DO NOT upload:
- venv/ or venv310/
- .env or .env.production
- __pycache__/
- credentials.json

### index.cgi line 1 must always be:
#!/home/dorjecha/public_html/app.cyber-tech.com/venv310/bin/python3.10

### After uploading new requirements.txt, run in cPanel Terminal:
cd ~/public_html/app.cyber-tech.com
venv310/bin/pip install -r requirements.txt