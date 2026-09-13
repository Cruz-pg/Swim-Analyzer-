import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../', import.meta.url))
const localPython = process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python'
const python = process.env.SWIMFORM_PYTHON || (existsSync(new URL(`../${localPython}`, import.meta.url)) ? localPython : 'python3')
const children = []
let stopping = false
function stop(code = 0) {
  if (stopping) return
  stopping = true
  process.exitCode = code
  children.forEach(child => child.kill('SIGTERM'))
  setTimeout(() => process.exit(code), 300).unref()
}
function run(command, args) {
  const child = spawn(command, args, { cwd: root, stdio: 'inherit', env: process.env })
  children.push(child)
  child.on('error', error => { console.error(error.message); stop(1) })
  child.on('exit', code => { if (!stopping) stop(code ?? 1) })
}
run(python, ['-m', 'uvicorn', 'app:app', '--host', '127.0.0.1', '--port', '8000', '--reload'])
run(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1'])
process.on('SIGINT', () => stop())
process.on('SIGTERM', () => stop())
