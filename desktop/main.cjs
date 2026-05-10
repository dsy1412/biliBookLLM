const { app, BrowserWindow, dialog } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const http = require("http");

const REPO_ROOT = __dirname ? path.resolve(__dirname, "..") : process.cwd();
const API_DIR = path.join(REPO_ROOT, "apps", "api");
const WEB_DIR = path.join(REPO_ROOT, "apps", "web");
const PYTHON_EXE = path.join(API_DIR, ".venv", "Scripts", "python.exe");
const API_URL = "http://127.0.0.1:8001/health";
const WEB_URL = "http://127.0.0.1:3000";

let mainWindow = null;
let apiProcess = null;
let webProcess = null;
let shuttingDown = false;

function logLine(prefix, data) {
  const text = data.toString().trim();
  if (!text) return;
  for (const line of text.split(/\r?\n/)) {
    console.log(`[${prefix}] ${line}`);
  }
}

function spawnLogged(command, args, options, prefix) {
  const child = spawn(command, args, {
    ...options,
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });

  child.stdout.on("data", (data) => logLine(prefix, data));
  child.stderr.on("data", (data) => logLine(prefix, data));
  child.on("exit", (code, signal) => {
    if (!shuttingDown) {
      console.log(`[${prefix}] exited with code=${code} signal=${signal}`);
    }
  });

  return child;
}

function loadingHtml(message) {
  return `data:text/html;charset=utf-8,${encodeURIComponent(`<!doctype html>
  <html>
    <head>
      <meta charset="utf-8" />
      <title>BiliBookLLM</title>
      <style>
        :root { color-scheme: dark; }
        body {
          margin: 0;
          font-family: Arial, Helvetica, sans-serif;
          background: #0b0b0f;
          color: #f4f4f5;
          display: grid;
          place-items: center;
          min-height: 100vh;
        }
        .wrap {
          width: min(560px, calc(100vw - 48px));
          border: 1px solid #27272a;
          border-radius: 16px;
          background: #15151a;
          padding: 32px;
          box-shadow: 0 20px 60px rgba(0,0,0,.35);
        }
        .badge {
          display: inline-block;
          padding: 8px 12px;
          border-radius: 999px;
          border: 1px solid #3f3f46;
          color: #d4d4d8;
          font-size: 13px;
          margin-bottom: 18px;
        }
        h1 {
          margin: 0 0 12px 0;
          font-size: 36px;
          line-height: 1.1;
        }
        p {
          margin: 0;
          color: #a1a1aa;
          font-size: 18px;
          line-height: 1.6;
        }
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="badge">BiliBookLLM desktop</div>
        <h1>Starting up</h1>
        <p>${message}</p>
      </div>
    </body>
  </html>`)}`;
}

function setWindowMessage(message) {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  void mainWindow.loadURL(loadingHtml(message));
}

function focusWindow() {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  mainWindow.show();
  if (mainWindow.isMinimized()) {
    mainWindow.restore();
  }
  mainWindow.focus();
}

function httpReady(url) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      res.resume();
      resolve(res.statusCode && res.statusCode < 500);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(2000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function waitForReady(url, timeoutMs, label) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (await httpReady(url)) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`${label} did not become ready within ${Math.round(timeoutMs / 1000)} seconds.`);
}

function hasBuiltNextApp() {
  return fs.existsSync(path.join(WEB_DIR, ".next", "BUILD_ID"));
}

async function ensureBackend() {
  if (!fs.existsSync(PYTHON_EXE)) {
    throw new Error(
      "Backend virtual environment not found. Run scripts\\bootstrap-desktop.ps1 once before launching the desktop app."
    );
  }

  setWindowMessage("Starting the local FastAPI backend...");
  apiProcess = spawnLogged(
    PYTHON_EXE,
    ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001"],
    { cwd: API_DIR, env: { ...process.env } },
    "api"
  );

  await waitForReady(API_URL, 60000, "Backend API");
}

async function ensureWeb() {
  const script = hasBuiltNextApp() ? "start" : "dev";
  const nextCmd =
    process.platform === "win32"
      ? path.join(REPO_ROOT, "apps", "web", "node_modules", ".bin", "next.cmd")
      : path.join(REPO_ROOT, "apps", "web", "node_modules", ".bin", "next");

  const nextArgs = script === "start" ? ["start", "-p", "3000"] : ["dev", "-p", "3000"];

  setWindowMessage("Starting the local web interface...");
  webProcess = spawnLogged(
    nextCmd,
    nextArgs,
    {
      cwd: WEB_DIR,
      env: {
        ...process.env,
        PORT: "3000",
        BACKEND_URL: "http://127.0.0.1:8001",
      },
      shell: process.platform === "win32",
    },
    "web"
  );

  await waitForReady(WEB_URL, 90000, "Web UI");
}

async function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 960,
    minWidth: 1100,
    minHeight: 760,
    backgroundColor: "#0b0b0f",
    autoHideMenuBar: true,
    show: true,
    title: "BiliBookLLM",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  await mainWindow.loadURL(loadingHtml("Preparing the app window..."));
  focusWindow();
}

async function shutdownChildren() {
  shuttingDown = true;
  for (const child of [webProcess, apiProcess]) {
    if (child && !child.killed) {
      child.kill();
    }
  }
}

app.on("before-quit", () => {
  shutdownChildren();
});

app.on("window-all-closed", () => {
  shutdownChildren();
  app.quit();
});

app.whenReady().then(async () => {
  try {
    await createMainWindow();
    await ensureBackend();
    await ensureWeb();
    setWindowMessage("Opening BiliBookLLM...");
    await mainWindow.loadURL(WEB_URL);
    focusWindow();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    setWindowMessage(message);
    await dialog.showMessageBox({
      type: "error",
      title: "BiliBookLLM failed to start",
      message,
      detail:
        "Make sure Python dependencies and the web dependencies are installed. Run scripts\\bootstrap-desktop.ps1 once before launching the app.",
    });
    await shutdownChildren();
  }
});
