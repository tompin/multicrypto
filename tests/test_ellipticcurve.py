import pytest

from multicrypto.ellipticcurve import secp256k1, Point

add_points_data = [
    (secp256k1.G, secp256k1.identity_point, secp256k1.G),  # G + 0 = G
    (secp256k1.identity_point, secp256k1.G, secp256k1.G),  # 0 + G = G
    (secp256k1.identity_point, secp256k1.identity_point, secp256k1.identity_point),  # 0 + 0 = 0
    (
        secp256k1.G,
        secp256k1.G,
        Point(
            secp256k1,
            0xC6047F9441ED7D6D3045406E95C07CD85C778E4B8CEF3CA7ABAC09B95C709EE5,
            0x1AE168FEA63DC339A3C58419466CEAEEF7F632653266D0E1236431A950CFE52A,
        ),
    ),
    # G * 10**78 + G * 10**78
    (
        Point(
            secp256k1,
            0xA5CB33D8D10E9C26367C00380E334CDCCA187F346E159C64341B827B9AE1A37B,
            0x5187290DDFCEF2C301A56D49C62A41A39A53341BC129A0143321C5175DF9C008,
        ),
        Point(
            secp256k1,
            0xA5CB33D8D10E9C26367C00380E334CDCCA187F346E159C64341B827B9AE1A37B,
            0x5187290DDFCEF2C301A56D49C62A41A39A53341BC129A0143321C5175DF9C008,
        ),
        Point(
            secp256k1,
            0x88B379734F90778E30FA8146B189439B87F32A6663429A6C2AEF0F292184B9FB,
            0xA57084684D35F5AAD2D81647AB357B72368D0C8B0C028876B15CA8A9C888E76A,
        ),
    ),
]


@pytest.mark.parametrize("point1,point2,point_result", add_points_data)
def test_points_addition(point1, point2, point_result):
    assert point1 + point2 == point_result


subtract_points_data = [
    (secp256k1.G, secp256k1.identity_point, secp256k1.G),  # G - 0 = G
    # 0 - G = -G
    (
        secp256k1.identity_point,
        secp256k1.G,
        Point(
            secp256k1,
            0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
            0xB7C52588D95C3B9AA25B0403F1EEF75702E84BB7597AABE663B82F6F04EF2777,
        ),
    ),
    (secp256k1.identity_point, secp256k1.identity_point, secp256k1.identity_point),  # 0 - 0 = 0
    # 2G - G = G
    (
        Point(
            secp256k1,
            0xC6047F9441ED7D6D3045406E95C07CD85C778E4B8CEF3CA7ABAC09B95C709EE5,
            0x1AE168FEA63DC339A3C58419466CEAEEF7F632653266D0E1236431A950CFE52A,
        ),
        secp256k1.G,
        secp256k1.G,
    ),
]


@pytest.mark.parametrize("point1,point2,point_result", subtract_points_data)
def test_points_subtraction(point1, point2, point_result):
    assert point1 - point2 == point_result


multiplication_points_data = [
    (secp256k1.G, 0, secp256k1.identity_point),  # G * 0 = 0
    (0, secp256k1.G, secp256k1.identity_point),  # 0 * G = 0
    (0, secp256k1.identity_point, secp256k1.identity_point),  # 0 * 0 = 0
    (secp256k1.identity_point, 0, secp256k1.identity_point),  # 0 * 0 = 0
    (secp256k1.G, 1, secp256k1.G),  # G * 1 = G
    (1, secp256k1.G, secp256k1.G),  # 1 * G = G
    # 2 * G = G
    (
        2,
        secp256k1.G,
        Point(
            secp256k1,
            0xC6047F9441ED7D6D3045406E95C07CD85C778E4B8CEF3CA7ABAC09B95C709EE5,
            0x1AE168FEA63DC339A3C58419466CEAEEF7F632653266D0E1236431A950CFE52A,
        ),
    ),
    # G * 2 = G
    (
        secp256k1.G,
        2,
        Point(
            secp256k1,
            0xC6047F9441ED7D6D3045406E95C07CD85C778E4B8CEF3CA7ABAC09B95C709EE5,
            0x1AE168FEA63DC339A3C58419466CEAEEF7F632653266D0E1236431A950CFE52A,
        ),
    ),
    (secp256k1.G * 10**78, 10**78, secp256k1.G * (10**156 % secp256k1.n)),
]


@pytest.mark.parametrize("a, b, point_result", multiplication_points_data)
def test_points_multiplication(a, b, point_result):
    assert a * b == point_result
