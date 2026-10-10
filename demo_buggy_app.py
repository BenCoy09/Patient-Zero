from flask import Flask, jsonify, request


def create_app():
    app = Flask(__name__)
    items = []

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.post("/items")
    def add_item():
        data = request.get_json(silent=True) or {}
        name = data.get("name")
        if not name:
            return jsonify(error="name is required"), 400
        item = {"id": len(items) + 1, "name": name}
        items.append(item)
        return jsonify(item), 201

    @app.get("/items")
    def list_items():
        return jsonify(items)

    return app
