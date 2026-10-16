"""Fácil Inscripción: separador de nombres, cliente resiliente y endpoint."""
import logging

import httpx
import pytest

from app.core.exceptions import ExternalServiceException
from app.dependencies.services import get_cedula_lookup_service
from app.main import app
from app.services.cedula_lookup_service import (
    CedulaLookupService, CedulaNotFound, LookupResult, LookupUnavailable, mask_identification,
)
from app.utils.names import split_full_name

CEDULA = "112345678"
URL = "https://hacienda.test/fe/ae"


# ══════════════════ separador de nombre / apellidos ══════════════════
@pytest.mark.parametrize("full,order,esperado", [
    ("ANA MARIA MORA SOLANO", "nombre_primero", ("Ana Maria", "Mora Solano")),
    ("JUAN PEREZ MORA", "nombre_primero", ("Juan", "Perez Mora")),
    ("MARIA DE LOS ANGELES SOLANO MORA", "nombre_primero", ("Maria de los Angeles", "Solano Mora")),
    ("ANA MORA DE LOS SANTOS", "nombre_primero", ("Ana", "Mora de los Santos")),
    ("ANA MORA", "nombre_primero", ("Ana", "Mora")),
    ("PEREZ MORA JUAN CARLOS", "apellidos_primero", ("Juan Carlos", "Perez Mora")),
    ("MORA ANA", "apellidos_primero", ("Ana", "Mora")),
    ("MADONNA", "nombre_primero", ("Madonna", "")),
    ("   ", "nombre_primero", ("", "")),
    ("  ana   maria   mora   solano ", "nombre_primero", ("Ana Maria", "Mora Solano")),
])
def test_split_full_name(full, order, esperado):
    parsed = split_full_name(full, order)
    assert (parsed.first_name, parsed.last_name) == esperado


# ══════════════════ cliente resiliente (transporte simulado) ══════════════════
def ok(nombre="ANA MARIA MORA SOLANO", tipo="01"):
    return httpx.Response(200, json={"nombre": nombre, "tipoIdentificacion": tipo, "regimen": {"codigo": 0}, "actividades": []})


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make(*script, **kw):
    """Servicio con transporte simulado. `script`: Response | Exception por llamada (la última se repite)."""
    calls, sleeps, clock = [], [], Clock()
    steps = list(script)

    def handler(request: httpx.Request):
        calls.append(request)
        step = steps.pop(0) if len(steps) > 1 else steps[0]
        if isinstance(step, Exception):
            raise step
        return step

    client = httpx.Client(transport=httpx.MockTransport(handler))
    defaults = dict(base_url=URL, max_retries=2, backoff_seconds=0.3, breaker_threshold=5,
                    breaker_cooldown_seconds=60, cache_ttl_seconds=100, negative_cache_ttl_seconds=30)
    svc = CedulaLookupService(client=client, clock=clock, sleep=sleeps.append, **{**defaults, **kw})
    return svc, calls, sleeps, clock


def test_encontrada_separa_nombre_y_envia_la_identificacion():
    svc, calls, _, _ = make(ok())
    r = svc.lookup(CEDULA)
    assert (r.first_name, r.last_name, r.full_name) == ("Ana Maria", "Mora Solano", "ANA MARIA MORA SOLANO")
    assert r.identification_type == "fisica"
    assert len(calls) == 1 and calls[0].url.params["identificacion"] == CEDULA


def test_respeta_el_orden_de_nombre_configurado():
    svc, *_ = make(ok("MORA SOLANO ANA MARIA"), name_order="apellidos_primero")
    r = svc.lookup(CEDULA)
    assert (r.first_name, r.last_name) == ("Ana Maria", "Mora Solano")


def test_persona_juridica_no_se_separa():
    svc, *_ = make(ok("ESTADO-MINISTERIO DE HACIENDA", tipo="02"))
    r = svc.lookup("2100042005")
    assert r.identification_type == "juridica" and r.last_name == ""


# ── caché ──
def test_cache_positiva_evita_repetir_la_consulta_y_expira():
    svc, calls, _, clock = make(ok())
    svc.lookup(CEDULA); svc.lookup(CEDULA); svc.lookup(CEDULA)
    assert len(calls) == 1
    clock.now += 101  # TTL = 100 s
    svc.lookup(CEDULA)
    assert len(calls) == 2


def test_cache_negativa_no_repite_cedulas_inexistentes():
    svc, calls, _, clock = make(httpx.Response(404, json={"error": "no existe"}))
    for _ in range(3):
        with pytest.raises(CedulaNotFound):
            svc.lookup(CEDULA)
    assert len(calls) == 1  # Hacienda advierte contra consultas repetidas de inexistentes
    clock.now += 31  # TTL negativo = 30 s
    with pytest.raises(CedulaNotFound):
        svc.lookup(CEDULA)
    assert len(calls) == 2


@pytest.mark.parametrize("respuesta", [httpx.Response(404), httpx.Response(400), httpx.Response(200, json={"nombre": ""}), httpx.Response(200, json={})])
def test_no_encontrada_en_todas_sus_variantes(respuesta):
    svc, *_ = make(respuesta)
    with pytest.raises(CedulaNotFound) as exc:
        svc.lookup(CEDULA)
    assert exc.value.code == "cedula_not_found" and "manualmente" in exc.value.detail


def test_las_fallas_nunca_se_guardan_en_cache():
    svc, calls, _, _ = make(httpx.Response(500), httpx.Response(500), httpx.Response(500), ok())
    with pytest.raises(LookupUnavailable):
        svc.lookup(CEDULA)
    assert svc.lookup(CEDULA).first_name == "Ana Maria" and len(calls) == 4


# ── reintentos ──
def test_reintenta_ante_5xx_con_backoff_exponencial_y_se_recupera():
    svc, calls, sleeps, _ = make(httpx.Response(503), httpx.Response(500), ok())
    assert svc.lookup(CEDULA).last_name == "Mora Solano"
    assert len(calls) == 3 and sleeps == [0.3, 0.6]


def test_agota_reintentos_y_lanza_error_de_dominio():
    svc, calls, sleeps, _ = make(httpx.Response(500))
    with pytest.raises(LookupUnavailable) as exc:
        svc.lookup(CEDULA)
    assert len(calls) == 3 and sleeps == [0.3, 0.6]
    assert exc.value.status_code == 503 and exc.value.code == "lookup_unavailable"
    assert isinstance(exc.value, ExternalServiceException)


@pytest.mark.parametrize("error", [
    httpx.ConnectTimeout("t"), httpx.ReadTimeout("t"), httpx.ConnectError("c"), httpx.RemoteProtocolError("p")])
def test_timeouts_y_errores_de_red_se_convierten_en_error_de_dominio(error):
    svc, calls, _, _ = make(error)
    with pytest.raises(LookupUnavailable):  # jamás debe escapar una excepción de httpx
        svc.lookup(CEDULA)
    assert len(calls) == 3


def test_respuesta_que_no_es_json_se_trata_como_falla():
    svc, *_ = make(httpx.Response(200, text="<html>Mantenimiento</html>"))
    with pytest.raises(LookupUnavailable):
        svc.lookup(CEDULA)
    svc2, *_ = make(httpx.Response(200, json=["no", "es", "objeto"]))
    with pytest.raises(LookupUnavailable):
        svc2.lookup(CEDULA)


def test_otros_4xx_no_se_reintentan():
    svc, calls, sleeps, _ = make(httpx.Response(403))
    with pytest.raises(LookupUnavailable):
        svc.lookup(CEDULA)
    assert len(calls) == 1 and sleeps == []


# ── 429 y cortacircuitos ──
def test_429_no_reintenta_y_pausa_segun_retry_after():
    svc, calls, _, clock = make(httpx.Response(429, headers={"Retry-After": "120"}), ok())
    with pytest.raises(LookupUnavailable) as exc:
        svc.lookup(CEDULA)
    assert exc.value.code == "lookup_rate_limited" and len(calls) == 1

    clock.now += 100  # aún dentro de los 120 s de Retry-After (> enfriamiento de 60 s)
    with pytest.raises(LookupUnavailable):
        svc.lookup("900000001")
    assert len(calls) == 1  # NO se vuelve a golpear a Hacienda (riesgo de bloqueo de IP)

    clock.now += 21
    assert svc.lookup("900000001").first_name == "Ana Maria" and len(calls) == 2


def test_429_sin_retry_after_usa_el_enfriamiento_configurado():
    svc, calls, _, clock = make(httpx.Response(429), ok())
    with pytest.raises(LookupUnavailable):
        svc.lookup(CEDULA)
    clock.now += 59
    with pytest.raises(LookupUnavailable):
        svc.lookup("900000001")
    clock.now += 2
    svc.lookup("900000001")
    assert len(calls) == 2


def test_cortacircuitos_se_abre_tras_n_fallas_y_se_cierra_al_recuperarse():
    svc, calls, _, clock = make(httpx.Response(500), max_retries=0, breaker_threshold=3)
    for i in range(3):
        with pytest.raises(LookupUnavailable):
            svc.lookup(f"90000000{i}")
    assert len(calls) == 3

    with pytest.raises(LookupUnavailable):  # abierto: ni siquiera se intenta
        svc.lookup("900000009")
    assert len(calls) == 3

    clock.now += 61  # fin del enfriamiento -> una prueba
    svc2, calls2, _, clock2 = svc, calls, None, clock
    svc2._client = httpx.Client(transport=httpx.MockTransport(lambda r: (calls2.append(r), ok())[1]))
    assert svc2.lookup("900000009").first_name == "Ana Maria"
    assert svc2.lookup("900000008").first_name == "Ana Maria"  # circuito cerrado: opera normal
    assert len(calls2) == 5


def test_si_la_prueba_tras_el_enfriamiento_falla_se_reabre_de_inmediato():
    svc, calls, _, clock = make(httpx.Response(500), max_retries=0, breaker_threshold=2)
    for i in range(2):
        with pytest.raises(LookupUnavailable):
            svc.lookup(f"90000000{i}")
    clock.now += 61
    with pytest.raises(LookupUnavailable):
        svc.lookup("900000005")  # prueba (half-open) que falla
    n = len(calls)
    with pytest.raises(LookupUnavailable):
        svc.lookup("900000006")
    assert len(calls) == n  # reabierto sin gastar otra llamada


def test_un_404_cuenta_como_servicio_sano_y_reinicia_las_fallas():
    svc, calls, _, _ = make(httpx.Response(500), httpx.Response(404), httpx.Response(500), httpx.Response(500),
                            max_retries=0, breaker_threshold=3)
    with pytest.raises(LookupUnavailable): svc.lookup("900000001")
    with pytest.raises(CedulaNotFound): svc.lookup("900000002")      # reinicia el contador
    with pytest.raises(LookupUnavailable): svc.lookup("900000003")
    with pytest.raises(LookupUnavailable): svc.lookup("900000004")
    ok_svc_calls = len(calls)
    assert ok_svc_calls == 4  # 2 fallas seguidas < umbral 3: el circuito sigue cerrado


def test_deshabilitado_no_hace_ninguna_llamada():
    svc, calls, _, _ = make(ok(), enabled=False)
    with pytest.raises(LookupUnavailable) as exc:
        svc.lookup(CEDULA)
    assert exc.value.code == "lookup_disabled" and calls == []


def test_el_cache_tiene_limite_de_tamano():
    svc, *_ = make(ok(), cache_max_entries=3)
    for i in range(10):
        svc.lookup(f"90000000{i}")
    assert len(svc._cache) <= 3


# ── privacidad en logs ──
def test_los_logs_no_contienen_la_cedula_completa(caplog):
    svc, *_ = make(httpx.Response(500), max_retries=0)
    with caplog.at_level(logging.DEBUG, logger="app.services.cedula_lookup_service"):
        with pytest.raises(LookupUnavailable):
            svc.lookup(CEDULA)
    assert "112***678" in caplog.text and CEDULA not in caplog.text
    assert mask_identification("112345678") == "112***678" and mask_identification("123") == "***"


# ══════════════════ endpoint ══════════════════
class FakeLookup:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, []

    def lookup(self, ident):
        self.calls.append(ident)
        if self.error:
            raise self.error
        return self.result


def _persona(**kw):
    base = dict(identification=CEDULA, full_name="ANA MARIA MORA SOLANO", first_name="Ana Maria",
                last_name="Mora Solano", identification_type="fisica")
    return LookupResult(**{**base, **kw})


@pytest.fixture
def fake(request):
    """Reemplaza el servicio singleton: ninguna prueba toca la red real."""
    f = FakeLookup(result=_persona())
    app.dependency_overrides[get_cedula_lookup_service] = lambda: f
    yield f
    app.dependency_overrides.pop(get_cedula_lookup_service, None)


EP = "/api/v1/members/cedula-lookup"


def test_endpoint_exito(client, h_recep, fake):
    r = client.get(f"{EP}/{CEDULA}", headers=h_recep)
    assert r.status_code == 200
    assert r.json() == {
        "identification": CEDULA, "full_name": "ANA MARIA MORA SOLANO", "first_name": "Ana Maria",
        "last_name": "Mora Solano", "birth_date": None, "identification_type": "fisica",
        "source": "hacienda", "needs_review": True, "already_registered": False,
        "existing_member_id": None, "existing_member_deleted": False}
    assert fake.calls == [CEDULA]


def test_la_ruta_no_se_confunde_con_un_id_de_socio(client, h_recep, fake):
    assert client.get(f"{EP}/{CEDULA}", headers=h_recep).status_code != 422


def test_endpoint_normaliza_guiones(client, h_recep, fake):
    assert client.get(f"{EP}/1-1234-5678", headers=h_recep).status_code == 200
    assert fake.calls == [CEDULA]


@pytest.mark.parametrize("entrada", ["ABC123456", "12345678", "1234567890123", "1-23"])
def test_formato_invalido_ni_siquiera_consulta(client, h_recep, fake, entrada):
    r = client.get(f"{EP}/{entrada}", headers=h_recep)
    assert r.status_code == 422 and r.json()["code"] == "invalid_identification"
    assert "9 a 12 dígitos" in r.json()["detail"] and fake.calls == []


def test_no_encontrada_es_404_claro(client, h_recep, fake):
    fake.error = CedulaNotFound("No se encontró la cédula en el registro de consulta. Puede ingresar los datos manualmente", code="cedula_not_found")
    r = client.get(f"{EP}/{CEDULA}", headers=h_recep)
    assert r.status_code == 404 and r.json()["code"] == "cedula_not_found"
    assert "manualmente" in r.json()["detail"]


def test_servicio_caido_es_503_y_la_app_sigue_funcionando(client, h_recep, fake):
    fake.error = LookupUnavailable("El servicio de consulta de cédulas no está disponible en este momento. Ingrese los datos manualmente")
    r = client.get(f"{EP}/{CEDULA}", headers=h_recep)
    assert r.status_code == 503 and r.json()["code"] == "lookup_unavailable"
    # la aplicación no se cae: el resto de endpoints responde con normalidad
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/members", headers=h_recep).status_code == 200
    fake.error = None  # y se recupera sola cuando el servicio vuelve
    assert client.get(f"{EP}/{CEDULA}", headers=h_recep).status_code == 200


def test_error_inesperado_del_cliente_tampoco_tumba_la_app(client, h_recep, fake):
    fake.error = RuntimeError("bug en el cliente")
    r = client.get(f"{EP}/{CEDULA}", headers=h_recep)
    assert r.status_code == 500 and r.json()["code"] == "internal_error" and "bug" not in r.text
    assert client.get("/api/v1/health").status_code == 200


def test_cedula_ya_registrada_no_consulta_a_hacienda(client, h_recep, fake, create_member):
    m = create_member(identification=CEDULA, first_name="Ana", last_name="Mora", birth_date="1995-04-12")
    r = client.get(f"{EP}/{CEDULA}", headers=h_recep)
    b = r.json()
    assert r.status_code == 200 and fake.calls == []
    assert (b["source"], b["already_registered"], b["needs_review"]) == ("local", True, False)
    assert b["existing_member_id"] == m["id"] and b["existing_member_deleted"] is False
    assert b["full_name"] == "Ana Mora" and b["birth_date"] == "1995-04-12"


def test_cedula_de_socio_dado_de_baja_se_indica(client, h_admin, fake, create_member):
    m = create_member(identification=CEDULA)
    client.delete(f"/api/v1/members/{m['id']}", headers=h_admin)
    b = client.get(f"{EP}/{CEDULA}", headers=h_admin).json()
    assert b["already_registered"] is True and b["existing_member_deleted"] is True and fake.calls == []


def test_persona_juridica_se_rechaza_como_socio(client, h_recep, fake):
    fake.result = _persona(identification="2100042005", full_name="ESTADO", first_name="Estado", last_name="", identification_type="juridica")
    r = client.get(f"{EP}/2100042005", headers=h_recep)
    assert r.status_code == 422 and r.json()["code"] == "lookup_legal_entity"


@pytest.mark.parametrize("fixture,status", [("h_admin", 200), ("h_recep", 200), ("h_trainer", 403), ("h_socio", 403)])
def test_permisos_del_lookup(client, request, fake, fixture, status):
    assert client.get(f"{EP}/{CEDULA}", headers=request.getfixturevalue(fixture)).status_code == status


def test_sin_token_el_lookup_exige_autenticacion(raw_client):
    assert raw_client.get(f"{EP}/{CEDULA}").status_code == 403


# ══════════════════ privacidad: log de acceso de uvicorn ══════════════════
def test_el_log_de_acceso_de_uvicorn_enmascara_la_cedula(caplog):
    from app.middleware.log_filters import MaskCedulaInAccessLog, mask_cedula_in_text
    assert mask_cedula_in_text("/api/v1/members/cedula-lookup/1-1234-5678?x=1") == "/api/v1/members/cedula-lookup/112***678?x=1"
    assert mask_cedula_in_text("/api/v1/members/cedula-lookup/112345678") == "/api/v1/members/cedula-lookup/112***678"
    assert mask_cedula_in_text("/api/v1/members?search=ana") == "/api/v1/members?search=ana"  # el resto no se toca

    rec = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                            ("127.0.0.1:1", "GET", "/api/v1/members/cedula-lookup/112345678", "1.1", 200), None)
    assert MaskCedulaInAccessLog().filter(rec) is True
    assert "112345678" not in rec.getMessage() and "112***678" in rec.getMessage()


def test_el_filtro_queda_instalado_en_el_logger_de_uvicorn():
    from app.middleware.log_filters import MaskCedulaInAccessLog
    import app.main  # noqa: F401
    assert any(isinstance(f, MaskCedulaInAccessLog) for f in logging.getLogger("uvicorn.access").filters)
