# Negotiation Deal Blueprint — Streamlit + MotherDuck

A mobile-friendly student form and password-gated instructor dashboard. Students submit deal terms; records are stored centrally in MotherDuck (DuckDB cloud), so all users see the same dataset.

## What is included

- Student form: group number, role, royalty, cash equity, commission, optional alternative structure, optional note.
- Central MotherDuck storage; records persist across app sessions.
- Duplicate-submit protection via a unique submission ID.
- Instructor dashboard with counts, averages, role chart, table, and CSV export.
- Instructor dashboard protected by a password stored in Streamlit secrets.

## 1. Requirements

- Python 3.10 or newer
- Git
- GitHub account
- MotherDuck account and access token
- Streamlit Community Cloud account

## 2. Create a MotherDuck token

1. Sign in to MotherDuck: https://motherduck.com/
2. Open your account/settings area and create an access token.
3. Copy it once and keep it private. Do not paste it into `app.py` or commit it to GitHub.
4. The app uses the token through `duckdb.connect("md:", config={"motherduck_token": token})`.

The app defaults to the MotherDuck database `my_db`. You can leave that setting as-is or change `MOTHERDUCK_DATABASE` to another database name that exists in your account. If using a different name, the app attempts to create it if it does not exist.

## 3. Run locally in VS Code (Windows PowerShell)

Open this project folder in VS Code. In Terminal → New Terminal, run:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml
```

If PowerShell blocks activation, run this once for the current terminal, then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Open `.streamlit/secrets.toml` and replace the example token and password with your real values. Then run:

```powershell
streamlit run app.py
```

Your browser should open at `http://localhost:8501`.

### Local test checklist

1. Choose **Submit deal**, enter a group and terms, tick the confirmation box, submit.
2. You should see “Deal Blueprint saved successfully.”
3. Choose **Instructor dashboard**, enter the `DASHBOARD_PASSWORD`.
4. Verify the submission appears and test CSV download.
5. Submit a second test with a different group. Confirm both appear.
6. Do not use a real student cohort until the test data is deleted or you have a clear plan for separating test submissions.

## 4. Push the project to GitHub

### Option A — New GitHub repository

Create an empty repository on GitHub (do not add a README if you already have one locally). Copy its HTTPS URL, then run these commands from the project folder:

```powershell
git init
git add app.py requirements.txt README.md .gitignore .streamlit/secrets.toml.example
git commit -m "Build negotiation deal blueprint app"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

Replace the remote URL with your repository URL.

### Option B — Repository already exists

If your existing repository is empty, use the commands above but skip `git init` if already initialized and update the remote if necessary:

```powershell
git status
git add app.py requirements.txt README.md .gitignore .streamlit/secrets.toml.example
git commit -m "Add negotiation deal blueprint app"
git branch -M main
git push -u origin main
```

If `origin` is not configured yet:

```powershell
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
```

If `origin` points to the wrong repository:

```powershell
git remote set-url origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
```

**Important:** Never run `git add .streamlit/secrets.toml`. The real secrets file is excluded by `.gitignore`; only the example file belongs in GitHub. Before pushing, run `git status` and verify `secrets.toml` is not listed.

## 5. Deploy on Streamlit Community Cloud

1. Push your code to GitHub.
2. Open https://share.streamlit.io/ and sign in with GitHub.
3. Click **Create app**.
4. Select your repository, branch `main`, and main file path `app.py`.
5. Open **Advanced settings** / **Secrets** before deploying.
6. Paste secrets in TOML format, replacing the example values:

```toml
MOTHERDUCK_TOKEN = "your-real-motherduck-token"
MOTHERDUCK_DATABASE = "my_db"
DASHBOARD_PASSWORD = "your-long-unique-dashboard-password"
```

7. Choose a memorable app subdomain if available, then click **Deploy**.
8. Wait for the app to start and test the public URL on your phone using mobile data or a private browser window.

Official deployment instructions: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app  
Secrets guide: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management

## 6. Share with students / QR code

After deployment, copy the `https://...streamlit.app` URL. Share it in your class group or create a QR code from that URL using a trusted QR-code generator. Test the QR code from a phone that is not logged into your GitHub account.

The app URL is the same for everyone; responses are saved to the same MotherDuck database. Students do not need GitHub, Python, or MotherDuck accounts.

## 7. Common issues

### “MotherDuck token is not configured”
- Local: confirm `.streamlit/secrets.toml` exists and contains `MOTHERDUCK_TOKEN = "..."`.
- Cloud: open your Streamlit app settings → Secrets and paste the TOML secrets there.
- Reboot the app after changing secrets if needed.

### Authentication / token error
- Confirm the token is active and copied fully.
- Do not add extra spaces inside the token.
- Check that your MotherDuck account has access to the database.

### “Catalog Error: database does not exist”
- Leave `MOTHERDUCK_DATABASE = "my_db"` for the default database, or use a valid database name. For a new non-default database, the app attempts to create it; if your account cannot create databases, create it in MotherDuck first.

### App works locally but not in Streamlit Cloud
- Check the app logs in Streamlit Community Cloud.
- Confirm the secrets are configured in the deployed app (local secrets are not uploaded with Git).
- Confirm the repository contains `app.py` and `requirements.txt` at the selected paths.

### Data doesn't appear
- Make sure the student saw the success message.
- Open the instructor dashboard and use the correct password.
- Confirm both local and deployed versions use the same MotherDuck account/database.
- Use a test submission first and confirm it is visible in the dashboard.

## 8. Important operational notes

- Anyone with the student link can submit. Do not collect personal or sensitive information.
- The dashboard password is a basic access gate, not enterprise-grade identity management. Share it only with the instructor.
- For a graded or sensitive collection, use institutional authentication and follow your instructor/institution's data-retention policy.
- The project does not include a public student response viewer; only the instructor dashboard shows submitted data.
- Test the deployed app with 2–3 devices before sharing with the full class.
