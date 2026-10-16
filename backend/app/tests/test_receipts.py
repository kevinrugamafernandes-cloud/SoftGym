"""Comprobante de pago: datos y PDF."""
import pytest

P = "/api/v1/payments"


def pay(client, headers, member, plan, **kw):
    r = client.post(P, json={"member_id": member["id"], "plan_id": plan["id"], "method": "efectivo", **kw}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_comprobante_json(client, clock, h_recep, create_member, plan):
    p = pay(client, h_recep, create_member(), plan)
    r = client.get(f"{P}/{p['id']}/receipt", headers=h_recep)
    assert r.status_code == 200
    b = r.json()
    assert {k: b["gym"][k] for k in ("name", "currency", "timezone")} == {"name": "Lion Fitness Center", "currency": "CRC", "timezone": "America/Costa_Rica"}
    assert b["payment"]["tax_rate"] == "13.00" and b["payment"]["subtotal"] == "22123.89" and b["payment"]["tax_amount"] == "2876.11"
    assert b["payment"]["receipt_code"] == "R-000001" and b["payment"]["amount"] == "25000.00"


def test_comprobante_pdf_es_un_pdf_valido_con_nombre_de_archivo(client, clock, h_recep, create_member, plan):
    p = pay(client, h_recep, create_member(), plan)
    r = client.get(f"{P}/{p['id']}/receipt.pdf", headers=h_recep)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"] == 'inline; filename="comprobante-R-000001.pdf"'
    assert r.content.startswith(b"%PDF") and r.content.rstrip().endswith(b"%%EOF") and len(r.content) > 1500


def _pdf_text(content: bytes) -> str:
    fitz = pytest.importorskip("pymupdf")  # PyMuPDF: solo para verificar el contenido del PDF
    with fitz.open(stream=content, filetype="pdf") as doc:
        assert doc.page_count == 1
        return doc[0].get_text()


def test_el_pdf_contiene_los_datos_correctos(client, clock, h_recep, create_member, plan):
    m = create_member(first_name="José", last_name="Muñoz", identification="112345678")
    p = pay(client, h_recep, m, plan, method="sinpe", reference="SINPE-889900", amount="20000")
    text = _pdf_text(client.get(f"{P}/{p['id']}/receipt.pdf", headers=h_recep).content)
    for expected in (
        "Lion Fitness Center", "Comprobante de pago", "R-000001", "10/10/2026", "José Muñoz", "112345678",
        "Mensual", "10/10/2026 al 08/11/2026", "SINPE Móvil", "SINPE-889900",
        "CRC 25 000,00", "CRC 5 000,00", "TOTAL PAGADO", "CRC 20 000,00", "Atendido por: Usuario receptionist",
    ):
        assert expected in text, expected
    assert "ANULADO" not in text


def test_pdf_de_un_pago_anulado_lleva_marca_y_motivo(client, clock, h_admin, h_recep, create_member, plan):
    p = pay(client, h_recep, create_member(), plan)
    client.post(f"{P}/{p['id']}/void", json={"reason": "Cobro duplicado por error"}, headers=h_admin)
    text = _pdf_text(client.get(f"{P}/{p['id']}/receipt.pdf", headers=h_recep).content)
    assert "ANULADO" in text and "Anulado el 10/10/2026" in text and "Motivo: Cobro duplicado por error" in text


def test_pdf_sin_descuento_no_muestra_lineas_de_descuento(client, clock, h_recep, create_member, plan):
    p = pay(client, h_recep, create_member(), plan)
    text = _pdf_text(client.get(f"{P}/{p['id']}/receipt.pdf", headers=h_recep).content)
    assert "Descuento" not in text and "Precio del plan" not in text


@pytest.mark.parametrize("fixture,status", [("h_admin", 200), ("h_recep", 200), ("h_trainer", 403), ("h_socio", 403)])
def test_permisos_del_comprobante(client, clock, request, h_recep, create_member, plan, fixture, status):
    p = pay(client, h_recep, create_member(), plan)
    h = request.getfixturevalue(fixture)
    assert client.get(f"{P}/{p['id']}/receipt.pdf", headers=h).status_code == status
    assert client.get(f"{P}/{p['id']}/receipt", headers=h).status_code == status


def test_comprobante_inexistente(client, h_recep):
    r = client.get(f"{P}/00000000-0000-0000-0000-000000000000/receipt.pdf", headers=h_recep)
    assert r.status_code == 404 and r.json()["code"] == "payment_not_found"


def test_la_fecha_de_anulacion_en_el_pdf_es_la_del_gimnasio_no_la_de_utc(client, clock, h_admin, h_recep, create_member, plan):
    """Anular a las 21:00 en Costa Rica = 03:00 UTC del día siguiente: el PDF debe decir el día de Costa Rica."""
    p = pay(client, h_recep, create_member(), plan)                         # 10/oct 12:00 CR
    clock.set_local(2026, 10, 10, 21)                                        # 21:00 CR = 03:00 UTC del 11/oct
    client.post(f"{P}/{p['id']}/void", json={"reason": "Cobro equivocado"}, headers=h_admin)
    text = _pdf_text(client.get(f"{P}/{p['id']}/receipt.pdf", headers=h_recep).content)
    assert "Anulado el 10/10/2026" in text and "11/10/2026" not in text
