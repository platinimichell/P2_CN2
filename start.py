#!/usr/bin/env python3
"""
Inicia o servidor local da aplicação de migração.
Acesse: http://localhost:5000
"""
import subprocess, sys, os, webbrowser, time, threading

def install_deps():
    print("[SETUP] Instalando dependências...")
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", "-r",
        os.path.join(os.path.dirname(__file__), "requirements.txt"), "-q"
    ])

def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://localhost:5000")
    print("\n  ✅ Navegador aberto em http://localhost:5000")

if __name__ == "__main__":
    install_deps()

    # Serve os arquivos estáticos junto com a API
    from flask import Flask, send_from_directory
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "api", os.path.join(os.path.dirname(__file__), "api", "index.py")
    )
    api_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api_module)
    app = api_module.app

    # Serve o frontend estático
    @app.route("/", defaults={"path": "index.html"})
    @app.route("/<path:path>")
    def serve_static(path):
        return send_from_directory(
            os.path.join(os.path.dirname(__file__), "public"), path
        )

    print("\n" + "═"*50)
    print("  Migration Tool — Servidor local")
    print("  URL: http://localhost:5000")
    print("  Pressione Ctrl+C para encerrar")
    print("═"*50 + "\n")

    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False)
