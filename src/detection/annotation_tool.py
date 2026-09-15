from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .annotation import (
    ANNOTATION_STATUS_ANNOTATED,
    ANNOTATION_STATUS_IN_PROGRESS,
    ANNOTATION_STATUS_NO_TARGET,
    ANNOTATION_STATUS_PENDING,
    HumanAnnotationManifest,
    HumanAnnotationRecord,
    HumanPolygonAnnotation,
    load_annotation_manifest,
    write_annotation_manifest,
)
from .annotation_validator import validate_annotation_record
from .dataset import PolygonPoint


HTML = r"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>ADWALLZ High-Rise Wall Annotation</title>
<style>
body {
  font-family: Arial, sans-serif;
  margin: 0;
  background: #f5f5f5;
}
header {
  background: #111;
  color: white;
  padding: 14px 20px;
}
main {
  display: grid;
  grid-template-columns: 280px 1fr;
  min-height: calc(100vh - 60px);
}
#sidebar {
  background: white;
  border-right: 1px solid #ddd;
  padding: 15px;
  overflow-y: auto;
}
.task {
  padding: 10px;
  margin-bottom: 6px;
  border: 1px solid #ddd;
  cursor: pointer;
  border-radius: 5px;
}
.task.active {
  border-color: #111;
  background: #eee;
}
#workspace {
  padding: 20px;
}
#canvasWrap {
  background: #222;
  padding: 10px;
  display: inline-block;
  max-width: calc(100vw - 350px);
}
canvas {
  max-width: 100%;
  height: auto;
  display: block;
  cursor: crosshair;
}
button {
  margin: 5px 5px 5px 0;
  padding: 9px 14px;
  cursor: pointer;
}
input {
  padding: 8px;
  width: 250px;
}
#status {
  margin: 10px 0;
  font-weight: bold;
}
#message {
  margin-top: 10px;
  padding: 8px;
  background: white;
  border: 1px solid #ddd;
}
.small {
  color: #666;
  font-size: 12px;
}
</style>
</head>
<body>
<header>
  <strong>ADWALLZ — High-Rise Wall Surface Annotation</strong>
</header>

<main>
<section id="sidebar">
  <h3>Images</h3>
  <div id="tasks"></div>
</section>

<section id="workspace">
  <div>
    <label>
      Annotator:
      <input id="annotator" placeholder="Name">
    </label>
  </div>

  <h2 id="title">Select an image</h2>
  <div id="meta" class="small"></div>
  <div id="status"></div>

  <div id="canvasWrap">
    <canvas id="canvas"></canvas>
  </div>

  <div>
    <button onclick="undoPoint()">Undo Point</button>
    <button onclick="finishPolygon()">Finish Polygon</button>
    <button onclick="clearCurrentPolygon()">Clear Current</button>
    <button onclick="clearAllPolygons()">Clear All</button>
    <button onclick="addPolygon()">Add Polygon</button>
    <button onclick="saveAnnotated()">Save Annotation</button>
    <button onclick="markNoTarget()">Mark No Target</button>
  </div>

  <div id="message"></div>
</section>
</main>

<script>
let tasks = [];
let current = null;
let image = new Image();
let canvas = document.getElementById("canvas");
let ctx = canvas.getContext("2d");

let polygons = [];
let currentPolygon = [];

async function loadTasks() {
  const response = await fetch("/api/tasks");
  tasks = await response.json();

  const container = document.getElementById("tasks");
  container.innerHTML = "";

  tasks.forEach(task => {
    const div = document.createElement("div");
    div.className = "task";
    div.id = "task-" + task.image_id;
    div.innerHTML =
      "<strong>" + task.image_id + "</strong> " +
      task.category +
      "<br><span class='small'>" +
      task.status +
      "</span>";

    div.onclick = () => selectTask(task.image_id);
    container.appendChild(div);
  });
}

async function selectTask(imageId) {
  const response = await fetch("/api/tasks/" + encodeURIComponent(imageId));
  current = await response.json();

  polygons = current.annotations.map(a =>
    a.polygon.map(p => ({x: p.x, y: p.y}))
  );

  currentPolygon = [];

  document.querySelectorAll(".task").forEach(e =>
    e.classList.remove("active")
  );

  const taskElement = document.getElementById("task-" + imageId);
  if (taskElement) taskElement.classList.add("active");

  document.getElementById("title").innerText =
    "Image " + current.image_id;

  document.getElementById("meta").innerText =
    current.category + " | " +
    current.image_width + " × " +
    current.image_height +
    " | split: " + current.split;

  document.getElementById("status").innerText =
    "Status: " + current.status;

  image.onload = () => {
    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;
    redraw();
  };

  image.src = "/" + current.relative_path;

  document.getElementById("message").innerText =
    current.category === "positive"
      ? "Click around each target wall surface. Finish each polygon separately."
      : "This image is classified as no-target.";
}

canvas.addEventListener("click", function(event) {
  if (!current || current.category !== "positive") return;

  const rect = canvas.getBoundingClientRect();

  const x = (event.clientX - rect.left) / rect.width;
  const y = (event.clientY - rect.top) / rect.height;

  currentPolygon.push({
    x: Math.max(0, Math.min(1, x)),
    y: Math.max(0, Math.min(1, y))
  });

  redraw();
});

function drawPolygon(points, closePolygon) {
  if (!points.length) return;

  ctx.beginPath();

  points.forEach((p, index) => {
    const x = p.x * canvas.width;
    const y = p.y * canvas.height;

    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });

  if (closePolygon && points.length >= 3) {
    ctx.closePath();
    ctx.stroke();
  } else {
    ctx.stroke();
  }

  points.forEach(p => {
    ctx.beginPath();
    ctx.arc(
      p.x * canvas.width,
      p.y * canvas.height,
      4,
      0,
      Math.PI * 2
    );
    ctx.fill();
  });
}

function redraw() {
  if (!image.complete) return;

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(image, 0, 0);

  polygons.forEach(poly => drawPolygon(poly, true));
  drawPolygon(currentPolygon, false);
}

function undoPoint() {
  currentPolygon.pop();
  redraw();
}

function clearCurrentPolygon() {
  currentPolygon = [];
  redraw();
}

function clearAllPolygons() {
  polygons = [];
  currentPolygon = [];
  redraw();
}

function finishPolygon() {
  if (currentPolygon.length < 3) {
    showMessage("A polygon requires at least 3 points.");
    return;
  }

  polygons.push(currentPolygon);
  currentPolygon = [];
  redraw();

  showMessage("Polygon added. Add another polygon if required.");
}

function addPolygon() {
  finishPolygon();
}

async function saveAnnotated() {
  if (!current) return;

  if (current.category === "positive" && currentPolygon.length >= 3) {
    finishPolygon();
  }

  const annotator =
    document.getElementById("annotator").value.trim();

  if (!annotator) {
    showMessage("Enter annotator name first.");
    return;
  }

  if (current.category === "positive" && polygons.length === 0) {
    showMessage("Positive image requires at least one polygon.");
    return;
  }

  const payload = {
    image_id: current.image_id,
    annotator: annotator,
    status:
      current.category === "positive"
        ? "annotated"
        : "no_target",
    annotations: polygons.map((poly, index) => ({
      annotation_id:
        current.image_id + "-poly-" + (index + 1),
      class_name: "wall_surface",
      polygon: poly,
      annotator: annotator,
      source: "human_reference",
      notes: ""
    }))
  };

  const response = await fetch("/api/save", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });

  const result = await response.json();

  if (!response.ok) {
    showMessage(result.error || "Save failed.");
    return;
  }

  showMessage("Saved successfully.");
  await loadTasks();
  await selectTask(current.image_id);
}

async function markNoTarget() {
  if (!current) return;

  if (current.category === "positive") {
    showMessage("Positive images cannot be marked no-target.");
    return;
  }

  const annotator =
    document.getElementById("annotator").value.trim();

  if (!annotator) {
    showMessage("Enter annotator name first.");
    return;
  }

  const response = await fetch("/api/save", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      image_id: current.image_id,
      annotator: annotator,
      status: "no_target",
      annotations: []
    })
  });

  const result = await response.json();

  if (!response.ok) {
    showMessage(result.error || "Save failed.");
    return;
  }

  showMessage("Marked no-target.");
  await loadTasks();
  await selectTask(current.image_id);
}

function showMessage(text) {
  document.getElementById("message").innerText = text;
}

loadTasks();
</script>
</body>
</html>
"""


class AnnotationServer:
    def __init__(
        self,
        dataset_root: Path,
        annotation_manifest_path: Path,
        manifest: HumanAnnotationManifest,
    ) -> None:
        self.dataset_root = dataset_root.resolve()
        self.annotation_manifest_path = annotation_manifest_path.resolve()
        self.manifest = manifest
        self.lock = threading.Lock()


def create_handler(server_state: AnnotationServer):
    class Handler(BaseHTTPRequestHandler):
        def _json(
            self,
            payload: object,
            status: int = 200,
        ) -> None:
            encoded = json.dumps(payload).encode("utf-8")

            self.send_response(status)
            self.send_header(
                "Content-Type",
                "application/json; charset=utf-8",
            )
            self.send_header(
                "Content-Length",
                str(len(encoded)),
            )
            self.end_headers()
            self.wfile.write(encoded)

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))

            if length > 2_000_000:
                raise ValueError("request body too large")

            raw = self.rfile.read(length)

            return json.loads(raw.decode("utf-8"))

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path

            if path == "/":
                encoded = HTML.encode("utf-8")

                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "text/html; charset=utf-8",
                )
                self.send_header(
                    "Content-Length",
                    str(len(encoded)),
                )
                self.end_headers()
                self.wfile.write(encoded)
                return

            if path == "/api/tasks":
                with server_state.lock:
                    payload = [
                        {
                            "image_id": record.image_id,
                            "category": record.category,
                            "status": record.status,
                        }
                        for record in server_state.manifest.images
                    ]

                self._json(payload)
                return

            if path.startswith("/api/tasks/"):
                image_id = path.split("/")[-1]

                try:
                    from .annotation import get_record

                    with server_state.lock:
                        record = get_record(
                            server_state.manifest,
                            image_id,
                        )

                    self._json(record.as_dict())
                except KeyError:
                    self._json(
                        {"error": "image not found"},
                        404,
                    )

                return

            if path.startswith("/images/") or "/" in path:
                relative = path.lstrip("/")

                candidate = (
                    server_state.dataset_root / relative
                ).resolve()

                try:
                    candidate.relative_to(
                        server_state.dataset_root
                    )
                except ValueError:
                    self._json(
                        {"error": "invalid path"},
                        403,
                    )
                    return

                if not candidate.is_file():
                    self._json(
                        {"error": "file not found"},
                        404,
                    )
                    return

                content_type = "application/octet-stream"

                if candidate.suffix.lower() in {
                    ".jpg",
                    ".jpeg",
                }:
                    content_type = "image/jpeg"
                elif candidate.suffix.lower() == ".png":
                    content_type = "image/png"
                elif candidate.suffix.lower() == ".webp":
                    content_type = "image/webp"

                data = candidate.read_bytes()

                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    content_type,
                )
                self.send_header(
                    "Content-Length",
                    str(len(data)),
                )
                self.end_headers()
                self.wfile.write(data)
                return

            self._json({"error": "not found"}, 404)

        def do_POST(self) -> None:
            if self.path != "/api/save":
                self._json({"error": "not found"}, 404)
                return

            try:
                payload = self._body()

                image_id = str(payload["image_id"])
                annotator = str(payload["annotator"]).strip()
                status = str(payload["status"])

                if not annotator:
                    raise ValueError("annotator is required")

                with server_state.lock:
                    from .annotation import get_record

                    record = get_record(
                        server_state.manifest,
                        image_id,
                    )

                    if record.category == "positive":
                        if status != ANNOTATION_STATUS_ANNOTATED:
                            raise ValueError(
                                "positive images must be saved as annotated"
                            )
                    else:
                        if status != ANNOTATION_STATUS_NO_TARGET:
                            raise ValueError(
                                "negative images must be saved as no_target"
                            )

                    annotations = []

                    for item in payload.get("annotations", []):
                        annotations.append(
                            HumanPolygonAnnotation(
                                annotation_id=str(
                                    item["annotation_id"]
                                ),
                                class_name=str(
                                    item.get(
                                        "class_name",
                                        "wall_surface",
                                    )
                                ),
                                polygon=tuple(
                                    PolygonPoint(
                                        x=float(point["x"]),
                                        y=float(point["y"]),
                                    )
                                    for point in item["polygon"]
                                ),
                                annotator=annotator,
                                source=str(
                                    item.get(
                                        "source",
                                        "human_reference",
                                    )
                                ),
                                notes=str(
                                    item.get("notes", "")
                                ),
                            )
                        )

                    updated = HumanAnnotationRecord(
                        image_id=record.image_id,
                        relative_path=record.relative_path,
                        category=record.category,
                        scene_group=record.scene_group,
                        image_width=record.image_width,
                        image_height=record.image_height,
                        status=status,
                        annotator=annotator,
                        annotations=annotations,
                        split=record.split,
                        source=record.source,
                        updated_at=record.updated_at,
                        notes=record.notes,
                    )

                    validation = validate_annotation_record(
                        updated
                    )

                    if not validation.valid:
                        raise ValueError(
                            "; ".join(validation.errors)
                        )

                    updated.touch()

                    from .annotation import upsert_record

                    upsert_record(
                        server_state.manifest,
                        updated,
                    )

                    write_annotation_manifest(
                        server_state.manifest,
                        server_state.annotation_manifest_path,
                    )

                self._json(
                    {
                        "saved": True,
                        "image_id": image_id,
                        "status": status,
                    }
                )

            except Exception as exc:
                self._json(
                    {
                        "saved": False,
                        "error": str(exc),
                    },
                    400,
                )

        def log_message(self, format: str, *args) -> None:
            return

    return Handler


def run_annotation_server(
    *,
    dataset_root: Path,
    annotation_manifest_path: Path,
    manifest: HumanAnnotationManifest,
    host: str = "0.0.0.0",
    port: int = 8765,
) -> None:
    state = AnnotationServer(
        dataset_root=dataset_root,
        annotation_manifest_path=annotation_manifest_path,
        manifest=manifest,
    )

    server = ThreadingHTTPServer(
        (host, port),
        create_handler(state),
    )

    print(
        f"High-Rise annotation tool running on "
        f"http://{host}:{port}"
    )
    print("Open the forwarded Codespace port in your browser.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping annotation server...")
    finally:
        server.server_close()
