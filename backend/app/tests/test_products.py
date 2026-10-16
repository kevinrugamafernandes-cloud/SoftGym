"""Catálogo de productos e inventario auditado."""
from app.models.user import UserRole
from app.tests.conftest import headers_for, make_gym, make_user

PR = "/api/v1/products"


def test_crear_producto_con_inventario_inicial(client, clock, h_admin, h_recep):
    r = client.post(PR, json={
        "name": "  Proteína   Whey 2 lb ", "sku": "PRO-001", "category": "Suplementos", "price": "32000",
        "cost": "21000", "cabys_code": "2399900000000", "initial_stock": 6, "min_stock": 2,
    }, headers=h_admin)
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["name"] == "Proteína Whey 2 lb" and p["tax_rate"] == "13.00" and p["stock"] == 6
    assert p["low_stock"] is False and p["is_active"] is True
    mv = client.get(f"{PR}/{p['id']}/movements", headers=h_recep).json()
    assert mv["total"] == 1 and mv["items"][0]["kind"] == "inicial" and mv["items"][0]["stock_after"] == 6
    assert mv["items"][0]["user_name"] == "Usuario admin"


def test_solo_el_administrador_gestiona_el_catalogo(client, clock, h_recep, h_trainer, create_product):
    p = create_product()
    assert client.post(PR, json={"name": "Agua", "price": "500"}, headers=h_recep).status_code == 403
    assert client.patch(f"{PR}/{p['id']}", json={"price": "1"}, headers=h_recep).status_code == 403
    assert client.post(f"{PR}/{p['id']}/stock", json={"kind": "entrada", "quantity": 1}, headers=h_recep).status_code == 403
    assert client.get(PR, headers=h_recep).status_code == 200            # la recepcionista consulta
    assert client.get(PR, headers=h_trainer).status_code == 403


def test_nombre_y_codigo_unicos_sin_distinguir_mayusculas(client, clock, h_admin, create_product):
    create_product(name="Agua 600 ml", sku="AG-600")
    r = client.post(PR, json={"name": "AGUA 600 ML", "price": "500"}, headers=h_admin)
    assert r.status_code == 409 and r.json()["code"] == "product_name_taken"
    r = client.post(PR, json={"name": "Agua grande", "sku": "ag-600", "price": "500"}, headers=h_admin)
    assert r.status_code == 409 and r.json()["code"] == "product_sku_taken"


def test_validaciones_en_espanol(client, clock, h_admin):
    r = client.post(PR, json={"name": "Barra", "price": "900", "cabys_code": "123"}, headers=h_admin)
    assert r.status_code == 422 and "CABYS" in r.json()["detail"]
    r = client.post(PR, json={"name": "Barra", "price": "-1"}, headers=h_admin)
    assert r.status_code == 422 and "Precio" in r.json()["detail"]
    r = client.post(PR, json={"name": "Barra", "price": "900", "tax_rate": "150"}, headers=h_admin)
    assert r.status_code == 422 and "IVA" in r.json()["detail"]


def test_editar_no_toca_el_stock(client, clock, h_admin, create_product):
    p = create_product(initial_stock=4)
    r = client.patch(f"{PR}/{p['id']}", json={"price": "1200", "stock": 999, "tax_rate": "0"}, headers=h_admin)
    assert r.status_code == 200
    assert r.json()["price"] == "1200.00" and r.json()["stock"] == 4 and r.json()["tax_rate"] == "0.00"
    assert client.patch(f"{PR}/{p['id']}", json={"name": None}, headers=h_admin).status_code == 422


def test_entrada_y_ajuste_de_stock_con_bitacora(client, clock, h_admin, create_product):
    p = create_product(initial_stock=3, cost="400")
    r = client.post(f"{PR}/{p['id']}/stock", json={"kind": "entrada", "quantity": 12, "unit_cost": "450", "notes": "Factura 123"}, headers=h_admin)
    assert r.status_code == 200 and r.json()["stock"] == 15 and r.json()["cost"] == "450.00"

    no_reason = client.post(f"{PR}/{p['id']}/stock", json={"kind": "ajuste", "counted_stock": 13}, headers=h_admin)
    assert no_reason.status_code == 422 and "motivo" in no_reason.json()["detail"]
    same = client.post(f"{PR}/{p['id']}/stock", json={"kind": "ajuste", "counted_stock": 15, "notes": "Conteo"}, headers=h_admin)
    assert same.status_code == 422 and same.json()["code"] == "no_stock_change"
    adj = client.post(f"{PR}/{p['id']}/stock", json={"kind": "ajuste", "counted_stock": 13, "notes": "2 vencidas"}, headers=h_admin)
    assert adj.json()["stock"] == 13

    mv = client.get(f"{PR}/{p['id']}/movements", headers=h_admin).json()["items"]
    assert [(m["kind"], m["quantity"], m["stock_after"]) for m in mv] == [("ajuste", -2, 13), ("entrada", 12, 15), ("inicial", 3, 3)]
    assert client.post(f"{PR}/{p['id']}/stock", json={"kind": "entrada"}, headers=h_admin).status_code == 422


def test_alerta_de_stock_bajo(client, clock, h_admin, create_product):
    low = create_product(name="Gatorade", initial_stock=2, min_stock=3)
    create_product(name="Agua", initial_stock=20, min_stock=3)
    inactive = create_product(name="Viejo", initial_stock=0, min_stock=1)
    client.patch(f"{PR}/{inactive['id']}", json={"is_active": False}, headers=h_admin)
    data = client.get(PR, headers=h_admin).json()
    assert data["low_stock_count"] == 1
    assert {p["name"]: p["low_stock"] for p in data["items"]} == {"Gatorade": True, "Agua": False, "Viejo": False}
    only = client.get(PR, params={"low_stock": True}, headers=h_admin).json()["items"]
    assert [p["id"] for p in only] == [low["id"]]
    assert len(client.get(PR, params={"active_only": True}, headers=h_admin).json()["items"]) == 2


def test_busqueda_sin_tildes_y_categorias(client, clock, h_admin, create_product):
    create_product(name="Proteína Whey", category="Suplementos", sku="PW1")
    create_product(name="Agua Cristal", category="Bebidas")
    create_product(name="Té frío", category="Bebidas")
    names = lambda q: [p["name"] for p in client.get(PR, params={"search": q}, headers=h_admin).json()["items"]]
    assert names("proteina") == ["Proteína Whey"]
    assert names("pw1") == ["Proteína Whey"]
    assert sorted(names("bebidas")) == ["Agua Cristal", "Té frío"]
    assert names("50%_") == []                                              # comodines escapados
    assert client.get(f"{PR}/categories", headers=h_admin).json() == ["Bebidas", "Suplementos"]
    assert len(client.get(PR, params={"category": "bebidas"}, headers=h_admin).json()["items"]) == 2


def test_aislamiento_entre_gimnasios(client, db, clock, create_product):
    p = create_product()
    hb = headers_for(make_user(db, UserRole.ADMIN, "admin-b@otro.com", gym=make_gym(db, "gym-b")))
    assert client.get(f"{PR}/{p['id']}", headers=hb).status_code == 404
    assert client.get(PR, headers=hb).json()["total"] == 0
    assert client.post(PR, json={"name": p["name"], "price": "1"}, headers=hb).status_code == 201   # mismo nombre, otro gym
