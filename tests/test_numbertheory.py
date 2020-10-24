from random import randint

import pytest

from multicrypto.ellipticcurve import secp256k1
from multicrypto.numbertheory import modular_inverse, modular_sqrt


def test_modular_inverse():
    n = secp256k1.n
    for i in range(100):
        a = randint(1, n)
        inv_a = modular_inverse(a, n)
        assert inv_a * a % n == 1


# All numbers with Legendre symbol 1
modular_sqrt_exists_data = [
    (87432535777948199077859334467609685666337724745541469173327025049110844846785, secp256k1.p),
    (15231347656644619387081489814083510755341109314328529093642931144875781544846, secp256k1.p),
    (29658265100089234582995724532279769752110778167346780333971418400623963307568, secp256k1.p),
    (100372059184905954807464784436905906401885246375647231279258280177182735337792, secp256k1.p),
    (6563385624456014786783321869882198377852969868671833201762171609922155978883, secp256k1.p),
    (48637223412012475908915380660087337928713130524625331453148440374556810251656, secp256k1.p),
    (74899221842787382617933781034309269940168089999002710263734841723686919466649, secp256k1.p),
    (70662362564359164773024269567256403995945544899232230604022306505072810041600, secp256k1.p),
    (63304974793595265488805775184100376177719048659832852516270198018363819021583, secp256k1.p),
    (30085594575992773443993594337760311858345824138386861673066098644505568540758, secp256k1.p),
    (29003073117844708665406582993502440205351437459585369035080049812481347395399, secp256k1.p),
    (36388534766239443406972277831349969808131678636841306180102417174314326109724, secp256k1.p),
    (29286661058501748097201869808655897442987605168881213182886176437714524169442, secp256k1.p),
    (12472026599249017007294096151874744470632587895760388903632287864038637093119, secp256k1.p),
    (22528288301408526929553360852454168247712676793263078885920522518416282663649, secp256k1.p),
    (17720328140621359316316169270336061442015579857931542915925124698077564146483, secp256k1.p),
    (10, 13),
    (56, 101),
    (1030, 10009),
    (44402, 100049),
    (665820697, 1000000009),
    (881398088036, 1000000000039)
]
no_modula_sqrt_solution_data = [
    (1032, 10009)
]


@pytest.mark.parametrize("a,p", modular_sqrt_exists_data)
def test_modular_sqrt_exists(a, p):
    sqrt = modular_sqrt(a, p)

    assert sqrt * sqrt % p == a, 'failure for a={}'.format(a)


@pytest.mark.parametrize("a,p", no_modula_sqrt_solution_data)
def test_modular_sqrt_no_existing(a, p):
    sqrt = modular_sqrt(a, p)

    assert sqrt == 0
