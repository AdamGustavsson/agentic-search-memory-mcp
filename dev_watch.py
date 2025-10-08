#!/usr/bin/env python3
"""
Development script with auto-reload for memory_server.py
Watches for file changes and automatically restarts the server.
"""
import sys
import subprocess
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class ServerReloader(FileSystemEventHandler):
    def __init__(self, server_script: Path):
        self.server_script = server_script
        self.process = None
        self.restart_server()
    
    def restart_server(self):
        """Restart the MCP server"""
        if self.process:
            print("🔄 Stopping server...")
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
        
        print(f"🚀 Starting server: {self.server_script}")
        self.process = subprocess.Popen(
            [sys.executable, str(self.server_script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        print("✅ Server started\n")
    
    def on_modified(self, event):
        """Handle file modification events"""
        if event.src_path.endswith('.py') and not event.is_directory:
            print(f"\n📝 Detected change in: {event.src_path}")
            time.sleep(0.5)  # Debounce
            self.restart_server()


if __name__ == "__main__":
    server_script = Path(__file__).parent / "memory_server.py"
    
    if not server_script.exists():
        print(f"❌ Error: {server_script} not found")
        sys.exit(1)
    
    print("👁️  Watching for changes in memory_server.py...")
    print("   Press Ctrl+C to stop\n")
    
    handler = ServerReloader(server_script)
    observer = Observer()
    observer.schedule(handler, path=str(server_script.parent), recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping...")
        observer.stop()
        if handler.process:
            handler.process.terminate()
    
    observer.join()

