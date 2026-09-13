# Swimform — setup after AirDrop

This copy contains the source code and dependency manifests, but deliberately does **not**
contain anyone's API key, Python virtual environment, `node_modules`, build output, or caches.

## macOS quick setup

1. Unzip the archive and open the `Swimform` folder.
2. Make sure these are installed:
   - Node.js 22.12 or newer
   - Python 3.9 or newer (Python 3.10+ enables the optional pose-estimation package)
3. In Terminal, change to this folder and run:

   ```bash
   ./setup-macos.command
   ```

4. Start the app:

   ```bash
   npm run dev
   ```

5. Open <http://127.0.0.1:5173>.
6. Add an OpenAI API key in the app's Settings dialog, or place it in `.env`:

   ```dotenv
   OPENAI_API_KEY=your-key-here
   ```

The setup script creates a local `.venv`, installs the Python packages from
`requirements.txt`, and installs the exact JavaScript dependency versions from
`package-lock.json`. Dependencies are downloaded separately on each recipient's Mac so native
packages match that computer.

If macOS will not run the helper, use these equivalent commands:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
npm ci
cp .env.example .env
npm run dev
```

See `README.md` for usage, production mode, tests, and troubleshooting.
