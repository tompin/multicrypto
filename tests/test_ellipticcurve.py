import pytest

from multicrypto.ellipticcurve import secp256k1, Point

add_points_data = [
    (secp256k1.G, secp256k1.identity_point, secp256k1.G),  # G + 0 = G
    (secp256k1.identity_point, secp256k1.G, secp256k1.G),  # 0 + G = G
    (secp256k1.identity_point, secp256k1.identity_point, secp256k1.identity_point),  # 0 + 0 = 0
    (secp256k1.G, secp256k1.G, Point(
        secp256k1,
        0xc6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee5,
        0x1ae168fea63dc339a3c58419466ceaeef7f632653266d0e1236431a950cfe52a)
     ),
    # G * 10**78 + G * 10**78
    (Point(secp256k1,
           0xa5cb33d8d10e9c26367c00380e334cdcca187f346e159c64341b827b9ae1a37b,
           0x5187290ddfcef2c301a56d49c62a41a39a53341bc129a0143321c5175df9c008),
     Point(secp256k1,
           0xa5cb33d8d10e9c26367c00380e334cdcca187f346e159c64341b827b9ae1a37b,
           0x5187290ddfcef2c301a56d49c62a41a39a53341bc129a0143321c5175df9c008),
     Point(secp256k1,
           0x88b379734f90778e30fa8146b189439b87f32a6663429a6c2aef0f292184b9fb,
           0xa57084684d35f5aad2d81647ab357b72368d0c8b0c028876b15ca8a9c888e76a))
]


@pytest.mark.parametrize("point1,point2,point_result", add_points_data)
def test_points_addition(point1, point2, point_result):
    assert point1 + point2 == point_result


subtract_points_data = [
    (secp256k1.G, secp256k1.identity_point, secp256k1.G),  # G - 0 = G
    # 0 - G = -G
    (secp256k1.identity_point, secp256k1.G, Point(
        secp256k1,
        0x79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798,
        0xb7c52588d95c3b9aa25b0403f1eef75702e84bb7597aabe663b82f6f04ef2777)),
    (secp256k1.identity_point, secp256k1.identity_point, secp256k1.identity_point),  # 0 - 0 = 0
    # 2G - G = G
    (Point(
        secp256k1,
        0xc6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee5,
        0x1ae168fea63dc339a3c58419466ceaeef7f632653266d0e1236431a950cfe52a),
     secp256k1.G, secp256k1.G)
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
    (2, secp256k1.G, Point(
        secp256k1,
        0xc6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee5,
        0x1ae168fea63dc339a3c58419466ceaeef7f632653266d0e1236431a950cfe52a)),
    # G * 2 = G
    (secp256k1.G, 2, Point(
        secp256k1,
        0xc6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee5,
        0x1ae168fea63dc339a3c58419466ceaeef7f632653266d0e1236431a950cfe52a)),
    (secp256k1.G * 10**78, 10**78, secp256k1.G * (10**156 % secp256k1.n)),
]


@pytest.mark.parametrize("a, b, point_result", multiplication_points_data)
def test_points_multiplication(a, b, point_result):
    assert a * b == point_result
