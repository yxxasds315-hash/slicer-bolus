import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { spawn } from 'child_process'
import path from 'path'

function slicerLauncherPlugin() {
  const launchScript = path.resolve(__dirname, '../scripts/launch_slicer.sh')

  return {
    name: 'slicer-launcher',
    configureServer(server: any) {
      server.middlewares.use('/api/launch', (_req: any, res: any) => {
        res.writeHead(200, { 'Content-Type': 'text/plain' })
        res.write('准备启动 3D Slicer...\n')
        // 先杀掉可能已在运行但未加载脚本的 Slicer
        const kill = spawn('pkill', ['-f', '/Applications/Slicer.app/Contents/MacOS/Slicer'], { stdio: 'ignore' })
        kill.on('close', () => {
          res.write('正在启动（请等待约 15 秒）...\n')
          const proc = spawn('bash', [launchScript], {
            detached: true,
            stdio: ['ignore', 'pipe', 'pipe'],
          })
          proc.stdout.on('data', (d: Buffer) => res.write(d))
          proc.stderr.on('data', (d: Buffer) => res.write(d))
          proc.on('close', () => res.end('\nSlicer exited'))
          proc.on('error', () => {
            res.write('\nFailed: Slicer not found at /Applications/Slicer.app')
            res.end()
          })
        })
      })

      server.middlewares.use('/api/browse-folder', (_req: any, res: any) => {
        const script = `
          set folderPath to POSIX path of (choose folder with prompt "选择文件夹:")
          return folderPath
        `
        const proc = spawn('osascript', ['-e', script])
        let result = ''
        proc.stdout.on('data', (d: Buffer) => { result += d.toString() })
        proc.on('close', () => {
          res.writeHead(200, { 'Content-Type': 'application/json' })
          res.end(JSON.stringify({ path: result.trim() }))
        })
        proc.on('error', () => {
          res.writeHead(500, { 'Content-Type': 'application/json' })
          res.end(JSON.stringify({ error: '平台不支持' }))
        })
      })

      server.middlewares.use('/api/health', async (_req: any, res: any) => {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 2000);
        try {
          const r = await fetch('http://localhost:8765/api/health', { signal: controller.signal });
          clearTimeout(timeout);
          const data = await r.json();
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify(data));
        } catch {
          clearTimeout(timeout);
          res.writeHead(503, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ status: 'offline' }));
        }
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), slicerLauncherPlugin()],
  server: {
    proxy: {
      '/api': 'http://localhost:8765',
    },
  },
})
