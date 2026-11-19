from fastapi.testclient import TestClient


def test_frontend_pages_and_assets_served(client: TestClient) -> None:
    paths = (
        "/app/index.html",
        "/app/services.html",
        "/app/login.html",
        "/app/register.html",
        "/app/create-order.html",
        "/app/client.html",
        "/app/master.html",
        "/app/admin.html",
        "/app/stats.html",
        "/app/kanban.html",
        "/app/js/config.js",
        "/app/js/api.js",
        "/app/js/ui.js",
        "/app/js/auth.js",
        "/app/js/create-order.js",
        "/app/js/client.js",
        "/app/js/master.js",
        "/app/js/admin.js",
        "/app/js/stats.js",
        "/app/js/kanban.js",
        "/app/css/styles.css",
        "/app/img/hero-repair.jpg",
        "/app/img/cat-smartphones.jpg",
        "/app/img/cat-laptops.jpg",
        "/app/img/cat-bga.jpg",
        "/app/img/cat-tablets.jpg",
        "/app/img/cat-pc.jpg",
    )
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, f"Не удалось загрузить {path}"
