from pathlib import Path
from flask import Flask, render_template, send_from_directory, abort, Markup, Response, request, send_file
import json, mimetypes, chardet
import pprint

APP_PORT = 8000
SERVER_ROOT = Path(__file__).parent.resolve()

app = Flask(__name__, template_folder="templates", static_folder="static")

# ---------- Helpers ----------
def list_dir(rel_path: Path):
    base = SERVER_ROOT / rel_path
    if not base.exists():
        abort(404)
    dirs = sorted([p for p in base.iterdir() if p.is_dir()])
    files = sorted([p for p in base.iterdir() if p.is_file()])
    return dirs + files

def detect_encoding(path: Path):
    raw = path.read_bytes()
    enc = chardet.detect(raw)["encoding"] or "utf-8"
    return raw.decode(enc, errors="replace")

# ---------- Routes ----------
@app.route("/", defaults={"subpath": ""})
@app.route("/<path:subpath>")
def index(subpath):
    rel_path = Path(subpath)
    abs_path = (SERVER_ROOT / rel_path).resolve()

    if SERVER_ROOT not in abs_path.parents and abs_path != SERVER_ROOT:
        abort(403)

    if abs_path.is_dir():
        entries = list_dir(rel_path)
        return render_template(
            "index.html",
            entries=entries,
            rel_path=rel_path,
        )

    if abs_path.suffix.lower() == ".json":
        return json_view(rel_path)

    mime = mimetypes.guess_type(abs_path.name)[0] or "application/octet-stream"
    return send_from_directory(abs_path.parent, abs_path.name, mimetype=mime)

@app.route("/json_raw/<path:subpath>")
def json_raw(subpath):
    abs_path = (SERVER_ROOT / Path(subpath)).resolve()
    if not abs_path.exists() or abs_path.suffix.lower() != ".json":
        abort(404)

    # pretty flag 또는 width 파라미터가 있으면 pprint 방식으로 포맷팅
    pretty_flag = request.args.get("pretty")
    width_arg = request.args.get("width", type=int)
    if pretty_flag in ("1", "true", "yes") or width_arg is not None:
        text = detect_encoding(abs_path)
        data = json.loads(text)
        width = width_arg or 10000
        pretty = pprint.pformat(data, indent=2, width=width, sort_dicts=False)
        encoded = pretty.encode("utf-8")

        def generate():
            chunk_size = 16 * 1024
            for i in range(0, len(encoded), chunk_size):
                yield encoded[i : i + chunk_size]

        return Response(generate(), mimetype="text/plain; charset=utf-8")

    # 그 외에는 디스크에서 바로 Range‐supported 스트리밍
    return send_file(
        abs_path,
        mimetype="application/json; charset=utf-8",
        conditional=True,
    )

def json_view(rel_path: Path):
    abs_path = SERVER_ROOT / rel_path
    try:
        # 윈도우 경로가 "\"로 찍히면 fetch URL이 깨집니다.
        return render_template(
            "json_view.html",
            rel_path=str(rel_path.as_posix()),   # URL 생성용
            filename=rel_path.name,              # 파일명 표시용
            full_path=str(abs_path.resolve())    # 전체 경로 표시용
        )
    except Exception as e:
        return render_template("error.html", msg=str(e)), 500

if __name__ == "__main__":
    print(f"Open → http://localhost:{APP_PORT}")
    app.run(host="0.0.0.0", port=APP_PORT, debug=False)
