"""
Bolus Designer — Flask 后端 (独立进程, 不依赖 Slicer 进程的 socket)
通过文件与 Slicer 通信
"""
import json, os, time, threading, queue, uuid
from datetime import datetime

FILES = {
    "config": "/tmp/bolus_config.json",
    "result": "/tmp/bolus_result.json",
    "status": "/tmp/bolus_status.json",
    "logs":   "/tmp/bolus_logs.jsonl",
}

try:
    from flask import Flask, request, jsonify, Response
    from waitress import serve
except ImportError:
    import sys
    print("需要 flask 和 waitress: pip install flask waitress")
    sys.exit(1)

app = Flask(__name__)
_sse_queues: list[queue.Queue] = []
_log_history: list[str] = []


def _broadcast(entry: str):
    _log_history.append(entry)
    with open(FILES["logs"], "a") as f:
        f.write(entry + "\n")
    dead = []
    for q in _sse_queues:
        try: q.put_nowait(entry)
        except queue.Full: dead.append(q)
    for q in dead: _sse_queues.remove(q)


def _read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except: return {}


def _write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)


@app.route('/api/health')
def health():
    slicer_alive = False
    try:
        mtime = os.path.getmtime(FILES["status"])
        slicer_alive = (time.time() - mtime) < 10
    except OSError:
        pass
    return jsonify(status='ok', slicer_running=slicer_alive)


@app.route('/api/slicer/status')
def slicer_status():
    return jsonify(_read_json(FILES["status"]))


def _dispatch_slicer(config, action, log_msg):
    """写 config → 轮询 result → 返回"""
    req_id = str(uuid.uuid4())[:8]

    def log_fn(level, msg):
        entry = json.dumps({"timestamp": datetime.now().strftime("%H:%M:%S"), "level": level, "message": msg})
        _broadcast(entry)

    log_fn("info", f"[{req_id}] {log_msg}")

    _write_json(FILES["config"], {"request_id": req_id, "action": action, "config": config, "timestamp": time.time()})

    if os.path.exists(FILES["result"]):
        os.remove(FILES["result"])

    timeout = 120 if action != "execute" else 300
    for _ in range(timeout):
        time.sleep(1)
        result = _read_json(FILES["result"])
        if result.get("request_id") == req_id:
            if result.get("status") == "completed":
                log_fn("success", f"[{req_id}] 完成: {len(result.get('output_files', []))} 条结果")
                return jsonify(result)
            elif result.get("status") == "error":
                log_fn("error", f"[{req_id}] {result.get('detail', '错误')}")
                return jsonify(result), 500

    log_fn("error", f"[{req_id}] 超时")
    return jsonify(status="error", detail=f"超时({timeout}秒)"), 504


@app.route('/api/execute', methods=['POST'])
def execute():
    config = request.get_json(force=True)
    return _dispatch_slicer(config, "execute", f"执行流水线: {config.get('design_method')}, {config.get('thickness_mm')}mm")


@app.route('/api/preview', methods=['POST'])
def preview():
    config = request.get_json(force=True)
    return _dispatch_slicer(config, "preview", f"阈值初筛: HU -300~3000")


@app.route('/api/scissors/activate', methods=['POST'])
def activate_scissors():
    config = request.get_json(force=True) if request.is_json else {}
    return _dispatch_slicer(config, "activate_scissors", "激活 Scissors 剪裁")


@app.route('/api/solidify', methods=['POST'])
def solidify():
    config = request.get_json(force=True)
    return _dispatch_slicer(config, "solidify", f"实心化: 填充内部空腔")


@app.route('/api/seal', methods=['POST'])
def seal():
    config = request.get_json(force=True)
    k1 = config.get("seal_kernel_1_mm", 15.0)
    k2 = config.get("seal_kernel_2_mm", 8.0)
    return _dispatch_slicer(config, "seal", f"二次封口: 大核{k1}mm + 中核{k2}mm")


@app.route('/api/preview/finalize', methods=['POST'])
def finalize_preview():
    config = request.get_json(force=True)
    return _dispatch_slicer(config, "finalize_preview", f"完成分割: 去杂讯+平滑")


@app.route('/api/roi/create', methods=['POST'])
def create_roi():
    config = request.get_json(force=True) if request.is_json else {}
    return _dispatch_slicer(config, "create_roi", "创建 Markups ROI")


@app.route('/api/logs/stream')
def log_stream():
    q: queue.Queue = queue.Queue(maxsize=200)
    _sse_queues.append(q)

    def generate():
        for entry in _log_history:
            yield f"data: {entry}\n\n"
        try:
            while True:
                yield f"data: {q.get()}\n\n"
        except GeneratorExit:
            _sse_queues.remove(q)

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


def main():
    print("=" * 50)
    print("Bolus Designer 后端")
    print("=" * 50)
    if os.environ.get("BOLUS_PROD"):
        serve(app, host="127.0.0.1", port=8765, threads=8)
    else:
        app.run(host="127.0.0.1", port=8765, debug=True, use_reloader=True)


if __name__ == "__main__":
    main()
