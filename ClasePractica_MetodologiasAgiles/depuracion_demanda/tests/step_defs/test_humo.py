from pytest_bdd import given, parsers, scenarios, then, when

scenarios("humo.feature")


@given(parsers.parse("un número {n:d}"), target_fixture="numero")
def numero(n):
    return n


@when(parsers.parse("se le suma {m:d}"), target_fixture="resultado")
def sumar(numero, m):
    return numero + m


@then(parsers.parse("el resultado es {r:d}"))
def resultado_es(resultado, r):
    assert resultado == r
