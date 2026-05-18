# Installation & Setup Guide

A complete step-by-step guide for beginners to get the AI Interview Prep System running on their computer.

---

## Table of Contents

1. [What You Will Need](#1-what-you-will-need)
2. [Step 1 — Install Python](#step-1--install-python)
3. [Step 2 — Install MongoDB](#step-2--install-mongodb)
4. [Step 3 — Download the Project](#step-3--download-the-project)
5. [Step 4 — Create a Virtual Environment](#step-4--create-a-virtual-environment)
6. [Step 5 — Install Dependencies](#step-5--install-dependencies)
7. [Step 6 — Download the Language Model](#step-6--download-the-language-model)
8. [Step 7 — Get Your API Keys](#step-7--get-your-api-keys)
9. [Step 8 — Configure the Environment File](#step-8--configure-the-environment-file)
10. [Step 9 — Run the App](#step-9--run-the-app)
11. [Step 10 — Open in Browser](#step-10--open-in-browser)
12. [Troubleshooting Common Errors](#troubleshooting-common-errors)

---

## 1. What You Will Need

Before starting, make sure you have the following:

| Requirement | Why It Is Needed | Free? |
|---|---|---|
| Python 3.10 or higher | The app is written in Python | Yes |
| MongoDB (local or Atlas) | Stores user accounts and interview data | Yes |
| Google Gemini API key | Powers AI question generation and evaluation | Yes (free tier) |
| AssemblyAI API key | Powers real-time voice transcription | Yes (free tier) |
| VAPI API key | Powers text-to-speech (optional) | Yes (free tier) |
| A terminal / command prompt | To run commands | Built into your OS |

> **Note:** VAPI is optional. If you skip it, the app will use your browser's built-in text-to-speech instead.

---

## Step 1 — Install Python

### Check if Python is already installed

Open your terminal (Command Prompt on Windows, Terminal on Mac/Linux) and type:

```bash
python --version
```

If you see something like `Python 3.11.4`, you are good. Skip to Step 2.

If you see an error or a version below 3.10, follow the steps below.

### Install Python (Windows)

1. Go to [https://www.python.org/downloads/](https://www.python.org/downloads/)
2. Click the big yellow **Download Python 3.x.x** button
3. Run the downloaded installer
4. **Important:** On the first screen, check the box that says **"Add Python to PATH"** before clicking Install
5. Click **Install Now**

### Install Python (Mac)

```bash
brew install python
```

If you do not have Homebrew, install it first from [https://brew.sh](https://brew.sh).

### Install Python (Linux / Ubuntu)

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

### Verify installation

```bash
python --version
```

You should see `Python 3.10.x` or higher.

---

## Step 2 — Install MongoDB

The app needs MongoDB to store user accounts and interview results.

### Option A — MongoDB Community Server (runs on your computer)

1. Go to [https://www.mongodb.com/try/download/community](https://www.mongodb.com/try/download/community)
2. Select your operating system and click **Download**
3. Run the installer and follow the default steps
4. Make sure you check **"Install MongoDB as a Service"** during setup (Windows)
5. After installation, MongoDB will start automatically

To verify MongoDB is running, open a new terminal and type:

```bash
mongosh
```

You should see a `>` prompt. Type `exit` to quit.

### Option B — MongoDB Atlas (free cloud database, no installation)

If you prefer not to install MongoDB locally, use the free cloud service:

1. Go to [https://www.mongodb.com/atlas](https://www.mongodb.com/atlas) and create a free account
2. Create a **free M0 cluster**
3. Under **Database Access**, create a username and password
4. Under **Network Access**, click **Add IP Address** → **Allow Access from Anywhere** (for development)
5. Click **Connect** on your cluster → **Compass** or **Drivers** → copy the connection string

The connection string will look like:
```
mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/interview_app
```

You will use this in Step 8.

---

## Step 3 — Download the Project

### Option A — Using Git (recommended)

If you have Git installed:

```bash
git clone <your-repository-url>
cd project
```

### Option B — Download as ZIP

1. Go to the repository page
2. Click the green **Code** button → **Download ZIP**
3. Extract the ZIP file to a folder of your choice
4. Open your terminal and navigate to the extracted folder:

```bash
cd path/to/project
```

**Example on Windows:**
```bash
cd C:\Users\YourName\Downloads\project
```

**Example on Mac/Linux:**
```bash
cd ~/Downloads/project
```

---

## Step 4 — Create a Virtual Environment

A virtual environment keeps the project's dependencies separate from your system Python. This prevents conflicts with other Python projects.

### Windows

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> **Windows PowerShell error?** If you see a message about script execution being disabled, run this first, then try again:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### Mac / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### How to know it worked

After activation, your terminal prompt will change. You will see `(.venv)` at the beginning:

```
(.venv) C:\Users\YourName\project>
```

> **Important:** Every time you open a new terminal to work on this project, you must activate the virtual environment again using the same command above.

---

## Step 5 — Install Dependencies

Make sure your virtual environment is active (you see `(.venv)` in the prompt), then run:

```bash
pip install -r requirements.txt
```

This will download and install all the libraries the app needs. It may take 2–5 minutes depending on your internet speed.

### Verify installation

```bash
pip list
```

You should see packages like `Flask`, `pymongo`, `google-generativeai`, `PyMuPDF`, etc. in the list.

---

## Step 6 — Download the Language Model

The app uses a spaCy language model for natural language processing. Download it with:

```bash
python -m spacy download en_core_web_sm
```

Wait for it to finish. You will see a success message when it is done.

---

## Step 7 — Get Your API Keys

The app requires API keys from external services. Follow each guide below.

---

### Google Gemini API Key (Required)

This powers the AI question generation and answer evaluation.

1. Go to [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Sign in with your Google account
3. Click **Create API Key**
4. Copy the key — it looks like: `AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`

> The free tier includes generous daily limits, which is enough for development and personal use.

---

### AssemblyAI API Key (Required for voice features)

This powers real-time voice transcription during the interview.

1. Go to [https://www.assemblyai.com/](https://www.assemblyai.com/) and create a free account
2. After signing in, go to your **Dashboard**
3. Your API key is shown on the dashboard — copy it
4. It looks like: `a1b2c3d4e5f6g7h8i9j0...`

> The free tier provides enough transcription hours for development use.

---

### VAPI API Key (Optional — for text-to-speech)

This is used to read interview questions aloud using a natural AI voice.

> **You can skip this.** If you leave VAPI unconfigured, the app will use your browser's built-in text-to-speech automatically.

1. Go to [https://vapi.ai/](https://vapi.ai/) and create a free account
2. Navigate to the **API Keys** section in your dashboard
3. Create and copy your API key

---

## Step 8 — Configure the Environment File

The environment file is where you store all your API keys and settings. The app reads this file at startup.

### Create the file

Copy the example file to create your own:

**Windows:**
```bash
copy .env.example .env
```

**Mac / Linux:**
```bash
cp .env.example .env
```

### Edit the file

Open the `.env` file in any text editor (Notepad, VS Code, etc.) and fill in your values:

```env
# --- Database ---
# If using local MongoDB (Step 2, Option A):
MONGO_URI=mongodb://localhost:27017/interview_app

# If using MongoDB Atlas (Step 2, Option B), replace with your connection string:
# MONGO_URI=mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/interview_app

# --- Security ---
# Make this a long random string. You can type anything here for development.
# Example: mysecretkey_abc123xyz789
SECRET_KEY=change-me-to-a-long-random-string

# --- AI Services ---
# Paste your Google Gemini API key here
GEMINI_API_KEY=your-gemini-api-key-here

# Paste your AssemblyAI API key here
ASSEMBLYAI_API_KEY=your-assemblyai-api-key-here

# --- Voice (Optional) ---
# Leave these blank if you are skipping VAPI
VAPI_API_KEY=
VAPI_VOICE_ID=
VAPI_VOICE_PROVIDER=11labs
```

### Example of a filled-in `.env` file

```env
MONGO_URI=mongodb://localhost:27017/interview_app
SECRET_KEY=my_super_secret_key_12345
GEMINI_API_KEY=AIzaSyAbCdEfGhIjKlMnOpQrStUvWxYz123456
ASSEMBLYAI_API_KEY=a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6
VAPI_API_KEY=
VAPI_VOICE_ID=
VAPI_VOICE_PROVIDER=11labs
```

> **Never share your `.env` file.** It contains your private API keys. The file is already listed in `.gitignore` so it will not be uploaded to GitHub.

---

## Step 9 — Run the App

Make sure:
- Your virtual environment is active (`(.venv)` shows in your prompt)
- MongoDB is running (if using local install)
- Your `.env` file is filled in

Then start the development server:

```bash
python run.py
```

You should see output like this:

```
 * Running on http://127.0.0.1:5000
 * Debug mode: on
 * Restarting with stat
```

> **Keep this terminal open.** Closing it will stop the server.

---

## Step 10 — Open in Browser

Open your web browser and go to:

```
http://localhost:5000
```

You should see the home page of the AI Interview Prep System.

### What to try first

1. Click **Register** and create an account
2. Log in with your new account
3. Upload a PDF resume (5 MB max)
4. Wait for the system to extract your skills and generate questions
5. Click **Start Interview** and answer the questions

---

## Troubleshooting Common Errors

---

### `python` is not recognized / command not found

**Cause:** Python is not installed or not added to your PATH.

**Fix:** Reinstall Python and make sure to check **"Add Python to PATH"** during installation (Windows). On Mac/Linux, try `python3` instead of `python`.

---

### `.venv\Scripts\Activate.ps1 cannot be loaded because running scripts is disabled`

**Cause:** Windows PowerShell has script execution disabled by default.

**Fix:** Run this command once, then try activating again:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

### `pip install -r requirements.txt` fails with a build error

**Cause:** Some packages (like PyMuPDF) need system build tools.

**Fix on Windows:** Install the Microsoft C++ Build Tools:
1. Go to [https://visualstudio.microsoft.com/visual-cpp-build-tools/](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
2. Download and run the installer
3. Select **Desktop development with C++** and install
4. Restart your terminal and try `pip install` again

**Fix on Ubuntu/Debian:**
```bash
sudo apt install build-essential python3-dev
```

---

### `ModuleNotFoundError: No module named 'spacy'` or `en_core_web_sm`

**Cause:** The virtual environment is not active, or the spaCy model was not downloaded.

**Fix:**
```bash
# Activate the environment first
.\.venv\Scripts\Activate.ps1   # Windows
source .venv/bin/activate       # Mac/Linux

# Then install and download
pip install spacy
python -m spacy download en_core_web_sm
```

---

### `pymongo.errors.ServerSelectionTimeoutError`

**Cause:** The app cannot connect to MongoDB.

**Fix:**
- **Local MongoDB:** Make sure MongoDB is running. On Windows, search for **Services**, find **MongoDB**, and click **Start**. On Mac: `brew services start mongodb-community`. On Linux: `sudo systemctl start mongod`
- **MongoDB Atlas:** Double-check your connection string in `.env`. Make sure your IP address is whitelisted in Atlas under **Network Access**.

---

### `Error 500` or `Internal Server Error` when uploading a resume

**Cause:** Usually a missing or invalid Gemini API key.

**Fix:** Open `.env` and verify that `GEMINI_API_KEY` is set correctly. Make sure there are no extra spaces or quote marks around the key.

---

### The page loads but voice recording does not work

**Cause:** The browser needs microphone permission, and the AssemblyAI key may be missing.

**Fix:**
1. Click the padlock icon in your browser's address bar and allow microphone access
2. Check that `ASSEMBLYAI_API_KEY` is set in your `.env` file
3. Restart the server after editing `.env`

---

### The server starts but the browser shows `This site can't be reached`

**Cause:** The server is running on a different port, or the URL is wrong.

**Fix:** Make sure you are visiting `http://localhost:5000` (not `https://`). Check the terminal output — it will show the exact address the server is listening on.

---

### Changes to `.env` are not taking effect

**Cause:** The server is still running with the old configuration.

**Fix:** Stop the server with `Ctrl + C` in the terminal, then start it again with `python run.py`.

---

## Quick Reference — All Commands in Order

```bash
# 1. Navigate to the project folder
cd path/to/project

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
#    Windows:
.\.venv\Scripts\Activate.ps1
#    Mac/Linux:
source .venv/bin/activate

# 4. Install all dependencies
pip install -r requirements.txt

# 5. Download language model
python -m spacy download en_core_web_sm

# 6. Create environment file
#    Windows:
copy .env.example .env
#    Mac/Linux:
cp .env.example .env

# 7. Edit .env and add your API keys (use any text editor)

# 8. Start the server
python run.py

# 9. Open in browser
# http://localhost:5000
```

---

## Every Time You Come Back

When you return to work on or use this project in a new terminal session:

```bash
# Navigate to the project folder
cd path/to/project

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1   # Windows
source .venv/bin/activate       # Mac/Linux

# Start the server
python run.py
```

You do not need to reinstall dependencies or re-download the language model each time — only activate the virtual environment and run the server.
